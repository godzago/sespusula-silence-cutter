"""Review decisions belong to a specific source, analysis and media revision."""
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import uuid
from platform_support import state_root

from silence_core import APP, Cut, Project, Settings, US, UserError, atomic_json, load_json, timerange, normalize_cuts

STATE = state_root(APP)
PREFERENCES = STATE / 'preferences.json'


def load_preferences(path: Path = PREFERENCES) -> dict:
    if not path.exists():
        return {}
    try:
        data=load_json(path)
        audio=data.get('audio_settings',{})
        if not isinstance(audio,dict):
            raise UserError('Ses ayarlarının biçimi geçersiz.')
        chosen={k:v for k,v in audio.items() if k in ('threshold','minimum','maximum','padding','lead_padding','minimum_cut')}
        Settings(**chosen).validate(US)
        data['audio_settings']=chosen
        profile=data.get('keyboard_profile')
        if profile is not None and (not isinstance(profile,dict) or not isinstance(profile.get('threshold_db'),(int,float)) or
                                    not math.isfinite(profile['threshold_db']) or not -100<=profile['threshold_db']<=-1):
            raise UserError('Klavye profili geçersiz.')
        return data
    except (UserError,TypeError,ValueError):
        # Recover startup without destroying a user's settings evidence.
        backup=path.with_name(path.stem+'.invalid-'+uuid.uuid4().hex[:8]+path.suffix)
        path.rename(backup)
        return {'recovery_notice':f'Bozuk ayarlar yedeklendi: {backup.name}. Varsayılanlarla devam ediliyor.'}


def save_settings(settings: Settings, path: Path = PREFERENCES, **preferences) -> None:
    data=load_preferences(path)
    data.update(preferences)
    # Selection boundaries belong to this analysis, not the next project.
    data['audio_settings']={k:v for k,v in asdict(settings).items() if k not in ('start','end')}
    path.parent.mkdir(parents=True,exist_ok=True)
    atomic_json(path,data)


class ReviewSession:
    STATES=('correct','wrong','marker')

    def __init__(self, project: Project, track: int, settings: Settings, detected: list[Cut], state_dir: Path = STATE/'reviews',
                 proposals: list[dict] | None=None, context: dict | None=None):
        self.project=project
        self.track=track
        self.settings=settings
        self.candidates=[{'kind':'silence','text':'Konuşma dışı aralık','requires_approval':False} for _ in detected]
        for p in proposals or []:
            if p.get('kind') not in ('filler','retake'):
                raise UserError('Bilinmeyen konuşma önerisi türü.')
            if p['kind']=='retake':self.candidates.append(dict(p,requires_approval=False,marker_only=True))
        self.detected=list(detected)+[Cut(p['start'],p['end']) for p in self.candidates[len(detected):]]
        self.cuts=list(self.detected)
        self.decisions=['marker' if c.get('marker_only') else 'correct' for c in self.candidates]
        self.revision=0
        self._selected_revision=-1
        self._selected_cache=()
        self.state_dir=state_dir
        self.identity={
            'policy':'automatic-silence-repeat-markers-v1',
            'project_hashes': {str(p.relative_to(project.folder)):v for p,v in project.hashes.items()},
            'project_path':str(project.folder), 'track':track,
            'settings':{k:v for k,v in asdict(settings).items() if k!='maximum' or v is not None},
            'media':{str(p):list(v) for p,v in project.media_stamps.items()},
        }
        if context:
            self.identity['analysis_context']=context
        if proposals:
            self.identity['proposals']=proposals
        key=hashlib.sha256(json.dumps(self.identity,sort_keys=True,ensure_ascii=False).encode('utf-8')).hexdigest()
        self.path=state_dir/(key+'.json')

    @property
    def enabled(self) -> set[int]:
        return {i for i,state in enumerate(self.decisions)
                if state=='correct' and not self.candidates[i].get('marker_only')}

    def selected_cuts(self) -> list[Cut]:
        if self._selected_revision!=self.revision:
            self._selected_cache=tuple(normalize_cuts([self.cuts[i] for i in self.enabled],self.project.duration))
            self._selected_revision=self.revision
        return list(self._selected_cache)

    def _changed(self):
        self.revision+=1

    def mark(self, i: int, state: str) -> None:
        if state not in self.STATES or not 0<=i<len(self.cuts):
            raise UserError('Geçersiz kesim kararı.')
        if self.candidates[i].get('marker_only'):
            self.decisions[i]='marker';return
        if self.decisions[i]!=state:
            self.decisions[i]=state;self._changed()

    def _validate_cut(self, i: int, cut: Cut) -> None:
        start,end=self.settings.validate(self.project.duration)
        if not start<=cut.start<cut.end<=end:
            raise UserError('Kesim analiz yapılan zaman aralığında olmalı.')
        for j,other in enumerate(self.cuts):
            # A proposed retake can contain silence candidates. Merge approved ranges at export.
            if (j!=i and self.candidates[j]['kind']=='silence' and self.candidates[i]['kind']=='silence' and
                    cut.start<other.end and cut.end>other.start):
                raise UserError('Bu aralık başka bir kesimle çakışıyor. Sınırları daraltın.')
        if self.candidates[i]['kind']=='silence' and self.settings.auto_jump_cut and self.settings.next_speech_padding is not None:
            return
        cursor=cut.start
        for seg in sorted(self.project.data['tracks'][self.track]['segments'],key=lambda s:s['target_timerange']['start']):
            a,b=timerange(seg['target_timerange'])
            if a<=cursor<b:
                cursor=max(cursor,b)
                if cursor>=cut.end:
                    return
        raise UserError('Kesim, seçilen kaynakta ses klibi bulunmayan bir boşluğu kapsayamaz.')

    def edit(self, i: int, start: int, end: int) -> None:
        if not 0<=i<len(self.cuts) or type(start) is not int or type(end) is not int:
            raise UserError('Geçersiz kesim.')
        if self.candidates[i].get('marker_only'):
            raise UserError('Tekrarlar yalnızca işarettir; otomatik kesilmez.')
        self._validate_cut(i,Cut(start,end))
        fps=self.project.fps
        a=round(math.ceil(start*fps/US-1e-8)*US/fps)
        b=round(math.floor(end*fps/US+1e-8)*US/fps)
        cut=Cut(a,b)
        self._validate_cut(i,cut)
        self.cuts[i]=cut
        self.decisions[i]='correct'
        self._changed()

    def add_manual(self, start: int, end: int, text: str) -> int:
        if not isinstance(text,str) or not text.strip():
            raise UserError('Çıkarmak için metinden bir bölüm seçin.')
        previous=(list(self.cuts),list(self.candidates),list(self.decisions))
        i=len(self.cuts)
        self.cuts.append(Cut(start,end))
        self.candidates.append({'kind':'manual','text':text.strip()[:1000],'requires_approval':False})
        self.decisions.append('correct')
        self._changed()
        try:
            self.edit(i,start,end)
            for j in range(i):
                if self.candidates[j]['kind']=='manual' and self.cuts[j]==self.cuts[i]:
                    self.cuts.pop();self.candidates.pop();self.decisions.pop()
                    self.decisions[j]='correct';i=j
                    break
            self.selected_cuts()
        except Exception:
            self.cuts,self.candidates,self.decisions=previous
            self._changed()
            raise
        return i

    def payload(self) -> dict:
        return {'version':3,'identity':self.identity,
                'detected_us':[[c.start,c.end] for c in self.detected],
                'reviewed_us':[[c.start,c.end] for c in self.cuts],
                'candidates':self.candidates,
                'decisions':list(self.decisions)}

    def save(self) -> None:
        self.state_dir.mkdir(parents=True,exist_ok=True)
        atomic_json(self.path,self.payload())

    def restore(self) -> bool:
        if not self.path.exists():
            return False
        data=load_json(self.path)
        if (data.get('version')!=3 or data.get('identity')!=self.identity or
                data.get('detected_us')!=[[c.start,c.end] for c in self.detected]):
            raise UserError('Kaydedilmiş inceleme bu analizle eşleşmiyor; kararlar uygulanmadı.')
        rows=data.get('reviewed_us'); decisions=data.get('decisions')
        if (not isinstance(rows,list) or not isinstance(decisions,list) or len(rows)<len(self.detected) or
                len(decisions)!=len(rows) or any(x not in self.STATES for x in decisions)):
            raise UserError('Kaydedilmiş kesim kararları bozuk; kararlar uygulanmadı.')
        candidates=list(self.candidates[:len(self.detected)])
        if data['version']==3:
            saved=data.get('candidates')
            if not isinstance(saved,list) or len(saved)!=len(rows) or saved[:len(self.detected)]!=candidates:
                raise UserError('Kaydedilmiş kesim türleri bu analizle eşleşmiyor.')
            for candidate in saved[len(self.detected):]:
                if (not isinstance(candidate,dict) or candidate.get('kind')!='manual' or
                        candidate.get('requires_approval') is not False or
                        not isinstance(candidate.get('text'),str) or not candidate['text'].strip() or
                        len(candidate['text'])>1000):
                    raise UserError('Kaydedilmiş metin seçimi geçersiz.')
                candidates.append({'kind':'manual','text':candidate['text'],'requires_approval':False})
        try:
            cuts=[Cut(*row) for row in rows]
            if any(type(c.start) is not int or type(c.end) is not int for c in cuts):
                raise ValueError('integer required')
        except (TypeError,ValueError):
            raise UserError('Kaydedilmiş kesim aralıkları geçersiz.')
        previous=(self.cuts,self.candidates)
        self.cuts=cuts;self.candidates=candidates
        try:
            for i,cut in enumerate(cuts):
                self._validate_cut(i,cut)
        except Exception:
            self.cuts,self.candidates=previous
            raise
        self.decisions=list(decisions)
        for i,c in enumerate(self.candidates):
            if c.get('marker_only'):self.decisions[i]='marker'
        self._changed()
        return True
