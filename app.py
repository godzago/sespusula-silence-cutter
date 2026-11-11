"""Turkish desktop interface; no network access is used at runtime."""
from pathlib import Path
import hashlib
import json
import copy
import math
import os
import queue
import tempfile
import threading
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from platform_support import AudioPlayer,open_folder,PLATFORM,VERSION

from silence_core import (Project, Settings, UserError, Cancelled, Cut, US,
                          discover_projects, create_copy, preview, project_content_file)
from review import ReviewSession, load_preferences, save_settings
from speech_analysis import analyze_speech
from transcript_review import transcript_sentences
from captions import build_captions, line_width, wrap_caption, validate_captions
from export_pipeline import export_copy


def seconds(value: str) -> float:
    parts = value.strip().replace(',', '.').split(':')
    if len(parts) > 3 or not all(parts):
        raise UserError('Zamanı saniye veya SS:DD:SN olarak yazın.')
    try:
        result = 0.0
        for part in parts:
            result = result * 60 + float(part)
        if not math.isfinite(result):
            raise UserError('Sonlu bir sayı yazın.')
        if len(parts)>1 and (any(float(p)<0 for p in parts) or any(float(p)>=60 for p in parts[1:])):
            raise UserError('Saat biçiminde dakika/saniye 0–59 aralığında olmalı.')
        return result
    except ValueError as exc:
        raise UserError('Zaman alanına sayı yazın. Örnek: 12,5 veya 01:20.') from exc


def clock(us: int) -> str:
    hours,total=divmod(round(us/1000),3600000)
    minutes,total=divmod(total,60000);secs,ms=divmod(total,1000)
    return f'{hours:02}:{minutes:02}:{secs:02}.{ms:03}'


class App(tk.Tk):
    def __init__(self, initial_project=None):
        super().__init__()
        self.title(('SesPusulaMac' if PLATFORM=='darwin' else 'SesPusula')+f' {VERSION} · CapCut Sessizlik Temizleyici')
        self.audio=AudioPlayer()
        width=min(1120,self.winfo_screenwidth()-40);height=min(900,self.winfo_screenheight()-100)
        left=max(0,(self.winfo_screenwidth()-width)//2)
        self.geometry(f'{width}x{height}+{left}+30')
        self.minsize(min(940,width),min(700,height))
        self.configure(bg='#101214')
        self.project = None
        self.caption_words=[]
        self.caption_cues=[]
        self.caption_signature=None
        self.caption_enabled=False
        self._caption_signature_key=None
        self._caption_signature_value=None
        self.cuts = []
        self.enabled = set()
        self.review_session = None
        self.transcript_selection_data = None
        self.transcript_ranges = []
        self.transcript_lines = []
        self.preferences = load_preferences()
        self.project_paths = []
        self.track_ids = []
        self.analyzed_track = None
        self.output = None
        self.busy = False
        self.closing = False
        self.cancel_event = threading.Event()
        self.events = queue.Queue()
        self.temp = tempfile.TemporaryDirectory(prefix='capcut-sessizlik-')
        self.protocol('WM_DELETE_WINDOW', self.close)
        self._style()
        self._build()
        self.bind('<Configure>',self.fit_header)
        self.refresh()
        if initial_project:
            self.load_project(Path(initial_project))
        if self.preferences.get('recovery_notice'):
            self.status.set(self.preferences['recovery_notice'])
        self._drain_after=self.after(80, self.drain)

    def _style(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('.', background='#101214', foreground='#e7edeb', font=('Segoe UI', 10))
        style.configure('TFrame', background='#101214')
        style.configure('TLabel', background='#101214', foreground='#cbd4d0')
        style.configure('Title.TLabel', font=('Segoe UI Semibold', 22), foreground='#f2f6f4')
        style.configure('Sub.TLabel', foreground='#8e9c96')
        style.configure('TButton', padding=(12,8), background='#282e33', borderwidth=0)
        style.map('TButton', background=[('active','#353e44'),('disabled','#1c2125')], foreground=[('disabled','#87958e')])
        style.configure('Accent.TButton', background='#40d9b0', foreground='#09251c', font=('Segoe UI Semibold', 11))
        style.map('Accent.TButton', background=[('active','#71e8c9'),('disabled','#243d35')])
        style.configure('TEntry', fieldbackground='#22272c', foreground='#f2f6f4', padding=7, insertcolor='white')
        style.configure('TCombobox', fieldbackground='#22272c', foreground='#f2f6f4', padding=7)
        style.map('TCombobox', fieldbackground=[('readonly','#22272c')], selectbackground=[('readonly','#22272c')], selectforeground=[('readonly','#f2f6f4')])
        style.configure('Treeview', background='#191d21', fieldbackground='#191d21', foreground='#e7edeb', rowheight=36, borderwidth=0, relief='flat')
        style.configure('Treeview.Heading', background='#22282d', foreground='#b2bfb8', padding=(10,10), relief='flat', font=('Segoe UI Semibold',9))
        style.map('Treeview', background=[('selected','#20443f')])
        style.configure('TProgressbar', background='#40d9b0', troughcolor='#22272c')
        style.configure('TNotebook',background='#101214',borderwidth=0)
        style.configure('TNotebook.Tab',background='#22282d',padding=(12,5))

        style.configure('Card.TFrame',background='#191d21')
        style.configure('Brand.TLabel',foreground='#40d9b0',font=('Segoe UI Semibold',10))
        style.configure('Badge.TLabel',foreground='#40d9b0',font=('Segoe UI Semibold',9))
        style.configure('CardSub.TLabel',background='#191d21',foreground='#8e9c96',font=('Segoe UI',9))
        style.configure('Eyebrow.TLabel',background='#191d21',foreground='#8e9c96',font=('Segoe UI Semibold',9))
        style.configure('Metric.TLabel',background='#191d21',foreground='#f2f6f4',font=('Segoe UI Semibold',20))
        style.configure('MetricAccent.TLabel',background='#191d21',foreground='#40d9b0',font=('Segoe UI Semibold',20))
        style.configure('TCheckbutton',background='#101214',foreground='#cbd4d0',padding=(4,5))
        style.map('TCheckbutton',background=[('active','#101214')],foreground=[('disabled','#87958e')])
        style.configure('TCombobox',borderwidth=0,arrowsize=14,arrowcolor='#8e9c96',relief='flat')
        style.configure('TButton',relief='flat',focusthickness=0)
        style.configure('TNotebook',tabmargins=(0,0,0,8))
        style.configure('TNotebook.Tab',padding=(16,9),borderwidth=0)
        style.map('TNotebook.Tab',background=[('selected','#28352f')],foreground=[('selected','#40d9b0')])
        style.layout('Treeview',[('Treeview.treearea',{'sticky':'nswe'})])
        style.configure('Vertical.TScrollbar',background='#353e44',troughcolor='#191d21',borderwidth=0,arrowsize=11)
        style.configure('Thin.Horizontal.TProgressbar',thickness=3,borderwidth=0)
        for name in ('TCombobox','Treeview','Treeview.Heading','TNotebook','TNotebook.Tab','Thin.Horizontal.TProgressbar'):
            style.configure(name,bordercolor='#22282d',lightcolor='#22282d',darkcolor='#22282d')

    def _build(self):
        root = ttk.Frame(self, padding=22)
        root.pack(fill='both', expand=True)
        self.intro_frame=ttk.Frame(root);self.intro_frame.pack(fill='x',pady=(0,16))
        ttk.Label(self.intro_frame,text='SESPUSULA',style='Brand.TLabel').pack(anchor='w')
        title_row=ttk.Frame(self.intro_frame);title_row.pack(fill='x',pady=(4,0))
        ttk.Label(title_row,text='Daha az boşluk. Daha çok içerik.',style='Title.TLabel').pack(side='left')
        ttk.Label(title_row,text='●  YEREL & ÇEVRİMDIŞI',style='Badge.TLabel').pack(side='right',padx=(12,0))
        self.project_row=ttk.Frame(root);self.project_row.pack(fill='x')
        self.project_row.columnconfigure(0,weight=3,uniform='inputs')
        self.project_row.columnconfigure(1,weight=2,uniform='inputs')
        row=ttk.Frame(self.project_row,style='Card.TFrame',padding=16)
        row.grid(row=0,column=0,sticky='nsew',padx=(0,6))
        ttk.Label(row,text='01  /  PROJE',style='Eyebrow.TLabel').pack(anchor='w',pady=(0,9))
        r=ttk.Frame(row,style='Card.TFrame');r.pack(fill='x')
        self.projects=ttk.Combobox(r,state='readonly');self.projects.pack(side='left',fill='x',expand=True)
        self.projects.bind('<<ComboboxSelected>>',self.select_project)
        self.refresh_btn=ttk.Button(r,text='↻',width=3,command=self.refresh);self.refresh_btn.pack(side='left',padx=6)
        self.browse_btn=ttk.Button(r,text='Klasör seç',command=self.browse);self.browse_btn.pack(side='left')
        self.path_text=tk.StringVar(value='Başlamak için bir CapCut projesi seçin.')
        self.path_label=ttk.Label(row,textvariable=self.path_text,style='CardSub.TLabel',wraplength=540)
        self.path_label.pack(anchor='w',pady=(8,0))
        row.bind('<Configure>',lambda event:self.path_label.configure(wraplength=max(180,event.width-32)))
        mic=ttk.Frame(self.project_row,style='Card.TFrame',padding=16)
        mic.grid(row=0,column=1,sticky='nsew',padx=(6,0))
        ttk.Label(mic,text='02  /  ANA MİKROFON',style='Eyebrow.TLabel').pack(anchor='w',pady=(0,9))
        self.tracks=ttk.Combobox(mic,state='readonly');self.tracks.pack(fill='x')
        self.tracks.bind('<<ComboboxSelected>>',lambda _:self.invalidate())
        ttk.Label(mic,text='Kesimler tüm katmanlara birlikte uygulanır.',style='CardSub.TLabel').pack(anchor='w',pady=(8,0))
        self.metrics_row=ttk.Frame(root);self.metrics_row.pack(fill='x',pady=(12,0))
        self.metric_vars=[tk.StringVar(value='—') for _ in range(3)]
        for i,label in enumerate(('KAYIT SÜRESİ','ÇIKARILAN SESSİZLİK','YENİ SÜRE')):
            self.metrics_row.columnconfigure(i,weight=1,uniform='metrics')
            card=ttk.Frame(self.metrics_row,style='Card.TFrame',padding=(16,10))
            card.grid(row=0,column=i,sticky='ew',padx=(0 if i==0 else 6,0 if i==2 else 6))
            ttk.Label(card,text=label,style='Eyebrow.TLabel').pack(anchor='w')
            ttk.Label(card,textvariable=self.metric_vars[i],style='Metric.TLabel' if i!=1 else 'MetricAccent.TLabel').pack(anchor='w',pady=(4,0))
        mode_row=ttk.Frame(root);mode_row.pack(fill='x',pady=(12,0))
        ttk.Label(mode_row,text='KESİM SEÇENEKLERİ',style='Sub.TLabel').pack(side='left')
        self.transcribe_var=tk.BooleanVar(value=self.preferences.get('transcribe_text',False) is True)
        self.suggest_var=tk.BooleanVar(value=True)
        self.suggest_check=ttk.Checkbutton(mode_row,text='Tekrarları işaretle',variable=self.suggest_var,command=self.update_buttons);self.suggest_check.pack(side='right')
        self.transcribe_check=ttk.Checkbutton(mode_row,text='Türkçe metin çıkar',variable=self.transcribe_var,command=self.invalidate);self.transcribe_check.pack(side='right',padx=(0,12))
        self.jump_cut_status=tk.StringVar(value='Ana sesteki sessizlik otomatik kesilir · Yeni konuşmadan önce 100 ms pay · Tekrarlar yalnızca işaretlenir.')
        self.rule_label=ttk.Label(root,textvariable=self.jump_cut_status,style='Sub.TLabel',wraplength=1000)
        self.rule_label.pack(anchor='w',pady=(6,0))
        self.compat_text=tk.StringVar(value='')
        self.compat_label=ttk.Label(root,textvariable=self.compat_text,wraplength=1030,foreground='#bfc9c3');self.compat_label.pack(anchor='w',pady=(8,8))
        body=ttk.Frame(root,style='Card.TFrame',padding=12)
        self.canvas=tk.Canvas(body,height=33,bg='#191d21',highlightthickness=0)
        self.canvas.pack(fill='x',pady=(0,8));self.canvas.bind('<Configure>',lambda _:self.draw())
        self.notebook=ttk.Notebook(body);self.notebook.pack(fill='both',expand=True)
        table=ttk.Frame(self.notebook);self.notebook.add(table,text='Kesim listesi')
        text_tab=ttk.Frame(self.notebook);self.notebook.add(text_tab,text='Türkçe metin')
        text_actions=ttk.Frame(text_tab);text_actions.pack(fill='x',pady=(0,4))
        self.transcript_listen_btn=ttk.Button(text_actions,text='Seçileni dinle',command=self.listen_transcript);self.transcript_listen_btn.pack(side='left')
        self.transcript_cut_btn=ttk.Button(text_actions,text='Bu bölümü çıkar',style='Accent.TButton',command=self.cut_transcript);self.transcript_cut_btn.pack(side='left',padx=8)
        self.transcript_status=tk.StringVar(value='Cümleye tıkla veya metinden bir bölüm seç.')
        ttk.Label(text_actions,textvariable=self.transcript_status,style='Sub.TLabel').pack(side='left',padx=8)
        text_body=ttk.Frame(text_tab);text_body.pack(fill='both',expand=True)
        self.transcript=tk.Text(text_body,height=5,wrap='word',bg='#191d21',fg='#e7edeb',font=('Segoe UI',11),borderwidth=0,padx=12,pady=8,state='disabled',exportselection=False)
        self.transcript.pack(side='left',fill='both',expand=True)
        text_scroll=ttk.Scrollbar(text_body,command=self.transcript.yview);text_scroll.pack(side='right',fill='y');self.transcript.configure(yscrollcommand=text_scroll.set)
        self.transcript.tag_configure('timestamp',foreground='#40d9b0')
        self.transcript.tag_configure('chosen',background='#20443f')
        self.transcript.bind('<ButtonRelease-1>',self.select_transcript)
        self.transcript.bind('<KeyRelease>',self.select_transcript)
        columns=('number','kind','decision','start','end','duration')
        self.tree=ttk.Treeview(table,columns=columns,show='headings',selectmode='browse',height=5)
        for col,label,width in [('number','#',45),('kind','Tür',115),('decision','İşlem',145),('start','Başlangıç',155),('end','Bitiş',155),('duration','Süre',100)]:
            self.tree.heading(col,text=label);self.tree.column(col,width=width,anchor='center',stretch=col not in ('number','decision'))
        self.tree.tag_configure('correct',foreground='#40d9b0')
        self.tree.tag_configure('wrong',foreground='#9aa9a1')
        self.tree.tag_configure('proposal',foreground='#bfc9c3')
        self.tree.pack(side='left',fill='both',expand=True)
        scroll=ttk.Scrollbar(table,orient='vertical',command=self.tree.yview);scroll.pack(side='right',fill='y');self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind('<space>',lambda _:self.toggle_selected())
        self.tree.bind('<Double-1>',lambda _:self.edit_selected())
        self.tree.bind('<Key-d>',lambda _:self.mark_selected('correct'))
        self.tree.bind('<Key-y>',lambda _:self.mark_selected('wrong'))
        self.tree.bind('<<TreeviewSelect>>',lambda _:self.selection_changed())
        tail=ttk.Frame(root);tail.pack(side='bottom',fill='x',before=root.winfo_children()[0])
        self.detail=tk.StringVar(value='Sessizlikler otomatik kesilir. Tekrarlar yalnızca işaretlenir; onay gerekmez.')
        ttk.Label(tail,textvariable=self.detail,wraplength=1000,style='Sub.TLabel').pack(anchor='w',pady=(5,0))
        review_row=ttk.Frame(tail);review_row.pack(fill='x',pady=(8,0))
        self.correct_btn=ttk.Button(review_row,text='Kesime dahil et (D)',command=lambda:self.mark_selected('correct'));self.correct_btn.pack(side='left')
        self.wrong_btn=ttk.Button(review_row,text='Bu aralığı koru (Y)',command=lambda:self.mark_selected('wrong'));self.wrong_btn.pack(side='left',padx=6)
        self.edit_btn=ttk.Button(review_row,text='Aralığı düzelt',command=self.edit_selected);self.edit_btn.pack(side='left',padx=6)
        self.next_btn=ttk.Button(review_row,text='Sonraki →',command=self.next_cut);self.next_btn.pack(side='right')
        self.summary=tk.StringVar(value='Önce projeyi ve konuşma katmanını seçin.')
        ttk.Label(tail,textvariable=self.summary,font=('Segoe UI Semibold',10)).pack(anchor='w',pady=(10,8))
        actions=ttk.Frame(tail);actions.pack(fill='x')
        self.analyze_btn=ttk.Button(actions,text='Analiz et',style='Accent.TButton',command=self.start_analysis);self.analyze_btn.pack(side='left')
        self.listen_btn=ttk.Button(review_row,text='Dinle',command=lambda:self.listen(False));self.listen_btn.pack(side='left',padx=8)
        self.after_btn=ttk.Button(review_row,text='Kesilmişini dinle',command=lambda:self.listen(True));self.after_btn.pack(side='left')
        self.caption_btn=ttk.Button(actions,text='Otomatik altyazı',command=self.start_captions);self.caption_btn.pack(side='left',padx=8)
        self.caption_toggle_var=tk.BooleanVar(value=False)
        self.caption_toggle=ttk.Checkbutton(actions,text='Ekle',variable=self.caption_toggle_var,command=self.toggle_captions);self.caption_toggle.pack(side='left')
        self.copy_btn=ttk.Button(actions,text='CapCut kopyası oluştur',style='Accent.TButton',command=self.write_copy);self.copy_btn.pack(side='right')
        footer=ttk.Frame(tail);footer.pack(fill='x',pady=(9,0))
        footer.columnconfigure(0,weight=1)
        self.status=tk.StringVar(value='Hazır · İşlem sırasında internet bağlantısı kullanılmaz.')
        status_label=ttk.Label(footer,textvariable=self.status,style='Sub.TLabel',wraplength=850)
        status_label.grid(row=0,column=0,sticky='ew')
        status_label.bind('<Configure>',lambda event:status_label.configure(wraplength=max(1,min(850,event.width))))
        self.cancel_btn=ttk.Button(footer,text='İptal',command=lambda:self.cancel_event.set());self.cancel_btn.grid(row=0,column=1,sticky='e',padx=(8,0))
        self.progress=ttk.Progressbar(tail,mode='indeterminate',style='Thin.Horizontal.TProgressbar');self.progress.pack(fill='x',pady=(7,0))
        body.pack(fill='both',expand=True)
        self.update_buttons()

    def fit_header(self,event):
        if event.widget is not self:return
        compact=event.height<800
        if compact:
            for widget in (self.intro_frame,self.rule_label,self.canvas):
                if widget.winfo_manager():widget.pack_forget()
        else:
            if not self.intro_frame.winfo_manager():self.intro_frame.pack(fill='x',pady=(0,16),before=self.project_row)
            if not self.rule_label.winfo_manager():self.rule_label.pack(anchor='w',pady=(6,0),before=self.compat_label)
            if not self.canvas.winfo_manager():self.canvas.pack(fill='x',pady=(0,8),before=self.notebook)
        self.selection_changed()

    def refresh(self):
        try:
            found=discover_projects()
            self.project_paths=[p for _,p in found]
            self.projects['values']=[f'{name}  —  {p.parent}' for name,p in found]
            if found:
                # Prefer the latest original project; don't silently clean a previous output again.
                choices=[i for i,(_,p) in enumerate(found) if not (p/'sessizlik_raporu.json').exists()]
                pick=max(choices or list(range(len(found))),key=lambda i:project_content_file(found[i][1]).stat().st_mtime_ns)
                self.projects.current(pick);self.select_project()
            else:self.status.set('Kayıtlı proje bulunamadı. “Klasör seç” ile taslak klasörünü açın.')
        except Exception as exc:self.error(exc)

    def browse(self):
        path=filedialog.askdirectory(title='CapCut proje klasörünü seçin')
        if path:self.load_project(Path(path))

    def select_project(self,event=None):
        i=self.projects.current()
        if i>=0:self.load_project(self.project_paths[i])

    def load_project(self,path):
        if self.busy:return
        previous=self.project
        try:
            p=Project(path)
            issues=p.compatibility()
            self.project=p
            self.caption_enabled=False
            if p.folder in self.project_paths:self.projects.current(self.project_paths.index(p.folder))
            else:self.projects.set(p.name)
            self.path_text.set(f'{p.name} · {clock(p.duration)} · {p.fps:g} fps · {p.folder}')
            sources=p.sources();self.track_ids=[i for _,i in sources];self.tracks['values']=[label for label,_ in sources]
            if sources:
                # Prefer audio tracks; the user must still pick the actual speech source.
                pick=next((j for j,(_,i) in enumerate(sources) if p.data['tracks'][i]['type']=='audio'),0)
                self.tracks.current(pick)
            else:self.tracks.set('Ses içeren katman bulunamadı')
            self.issues=issues
            if self.issues:
                self.compat_text.set('Analiz yapılabilir; proje kopyası için desteklenmeyen yapılar var. Ayrıntı: '+self.issues[0]+f' ({len(self.issues)} bulgu)')
                self.status.set('Kopya oluşturma engelli. Ayrıntıları analiz sonunda görebilirsiniz.')
            else:
                self.compat_text.set('Temel proje yapısı destekleniyor. Çıktı oluşturmadan önce CapCut’ı kaydedip kapatın.')
                self.status.set('Konuşma katmanını kontrol edin, ardından analiz edin.')
            self.invalidate()
        except Exception as exc:
            if previous and previous.folder in self.project_paths:self.projects.current(self.project_paths.index(previous.folder))
            self.error(exc)

    def invalidate(self):
        if self.busy:return
        self.cuts=[];self.enabled=set();self.analyzed_track=None;self.review_session=None;self.export_error=None
        self.caption_words=[];self.caption_cues=[];self.caption_signature=None
        self.update_metrics()
        self.jump_cut_status.set('Tüm zaman çizelgesi · Yeni konuşmadan önce 100 ms pay · Sessizlikler onaysız kesilir.')
        if hasattr(self,'tree'):
            self.tree.delete(*self.tree.get_children());self.summary.set('Ayarlar hazır. Analiz et düğmesine bas.');self.set_transcript('');self.draw();self.update_buttons()


    def get_settings(self):
        # Legacy saved ranges, thresholds and padding cannot limit or override automatic editing.
        return Settings(auto_jump_cut=True,next_speech_padding=.1)

    def current_caption_signature(self):
        if not self.project or self.tracks.current()<0:return None
        key=(self.project.folder,self.project.hashes[self.project.file],self.project.duration,
             self.track_ids[self.tracks.current()],self.review_session,
             self.review_session.revision if self.review_session else None)
        if self._caption_signature_key==key:return self._caption_signature_value
        cuts=self.review_session.selected_cuts() if self.review_session else []
        payload={'project_hash':self.project.hashes[self.project.file],'duration':self.project.duration,
                 'track':self.track_ids[self.tracks.current()],
                 'cuts':[[c.start,c.end] for c in cuts]}
        value=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        self._caption_signature_key=key;self._caption_signature_value=value
        return value

    def captions_ready(self):
        try:return bool(self.caption_cues) and self.caption_signature==self.current_caption_signature()
        except UserError:return False

    def toggle_captions(self):
        if self.busy:return
        self.caption_enabled=self.caption_toggle_var.get();self.update_buttons()
        if self.caption_enabled and not self.captions_ready():self.start_captions()
        elif not self.caption_enabled:self.status.set('Altyazı kapalı; kopyaya eklenmeyecek.')

    def start_captions(self):
        if not self.project or self.busy:return
        try:
            if self.tracks.current()<0:raise UserError('Önce ana mikrofonu seçin.')
            if self.captions_ready():
                if self.caption_enabled:self.show_captions()
                else:
                    self.caption_enabled=True;self.update_buttons()
                    self.status.set('Altyazı açık; proje kopyasına otomatik eklenecek.')
                return
            self.caption_enabled=True
            if self.caption_words:
                self.prepare_captions_for_copy();return
            project=self.project;track=self.track_ids[self.tracks.current()]
            # Captions cover the complete retained recording, even when silence analysis was limited.
            self.job('captions',lambda:analyze_speech(project,track,Settings(),self.cancel_event,
                lambda msg:self.events.put(('status',msg)),transcribe=True,suggest=False))
            self.status.set('Otomatik Türkçe altyazı hazırlanıyor; ilk çözümleme kayıt uzunluğuna göre zaman alabilir.')
        except UserError as exc:self.error(exc)

    def prepare_captions_for_copy(self):
        cuts=self.review_session.selected_cuts() if self.review_session else []
        self.caption_cues=build_captions(self.caption_words,cuts,self.project.duration,self.project.fps,line_width(self.project.data))
        if not self.caption_cues:raise UserError('Kalan konuşmadan altyazı oluşturulamadı.')
        self.caption_signature=self.current_caption_signature();self.caption_enabled=True
        self.update_buttons()
        self.status.set(f'{len(self.caption_cues)} altyazı hazır; kopyaya otomatik eklenecek. Metni düzenlemek istersen Altyazı düğmesine tekrar bas.')

    def show_captions(self):
        cuts=self.review_session.selected_cuts() if self.review_session else []
        signature=self.current_caption_signature()
        width=line_width(self.project.data)
        cues=copy.deepcopy(self.caption_cues) if self.captions_ready() else build_captions(
            self.caption_words,cuts,self.project.duration,self.project.fps,width)
        if not cues:raise UserError('Kesimlerden sonra altyazıya dönüştürülecek konuşma kalmadı.')
        dialog=tk.Toplevel(self);dialog.title('Otomatik Türkçe altyazı');dialog.transient(self);dialog.grab_set()
        dialog.geometry(f'820x{min(620,self.winfo_screenheight()-100)}');dialog.minsize(680,460)
        box=ttk.Frame(dialog,padding=14);box.pack(fill='both',expand=True)
        ttk.Label(box,text=f'{len(cues)} altyazı · Zamanlar kesilmiş çıktıya göre · Beyaz yazı, siyah kenarlık, alt orta',wraplength=770).pack(anchor='w')
        ttk.Label(box,text='Konuşma tanıma hata yapabilir. Bir satırı seçip metni düzeltin; kaydedince proje kopyasına eklenir.',style='Sub.TLabel',wraplength=770).pack(anchor='w',pady=(4,10))
        # Pack controls before the expanding table so they remain reachable on short displays.
        controls=ttk.Frame(box);controls.pack(side='bottom',fill='x')
        enabled=tk.BooleanVar(value=True)
        ttk.Checkbutton(controls,text='CapCut kopyasına altyazı ekle',variable=enabled).pack(anchor='w',pady=6)
        editor=tk.Text(controls,height=3,wrap='word',bg='#191d21',fg='#e7edeb',insertbackground='white',font=('Segoe UI',11))
        editor.pack(fill='x',pady=(0,6))
        row=ttk.Frame(controls);row.pack(fill='x')
        table=ttk.Treeview(box,columns=('start','end','text'),show='headings',selectmode='browse',height=7)
        for key,label,column_width in (('start','Başlangıç',110),('end','Bitiş',110),('text','Altyazı',510)):
            table.heading(key,text=label);table.column(key,width=column_width,stretch=key=='text')
        scroll=ttk.Scrollbar(box,command=table.yview);scroll.pack(side='right',fill='y');table.configure(yscrollcommand=scroll.set)
        table.pack(fill='both',expand=True,pady=(0,8))
        for i,c in enumerate(cues):table.insert('','end',iid=str(i),values=(clock(c['start']),clock(c['end']),c['text'].replace('\n',' / ')))
        editing=[None];original_text=['']
        def commit():
            i=editing[0]
            if i is None:return
            raw=editor.get('1.0','end-1c')
            if raw==original_text[0]:return
            text=wrap_caption(raw,width);cues[i]['text']=text
            table.set(str(i),'text',text.replace('\n',' / '));original_text[0]=raw
        def select(_=None):
            selected=table.selection()
            if not selected:return
            index=int(selected[0])
            if index==editing[0]:return
            try:commit()
            except UserError as exc:
                if editing[0] is not None:table.selection_set(str(editing[0]))
                messagebox.showerror('Altyazı metni',str(exc),parent=dialog);return
            editing[0]=index;original_text[0]=cues[index]['text']
            editor.delete('1.0','end');editor.insert('1.0',original_text[0])
        table.bind('<<TreeviewSelect>>',select)
        def save():
            try:
                commit()
                if signature!=self.current_caption_signature():raise UserError('Kesimler değişti; altyazıyı yeniden hazırlayın.')
                duration=self.project.duration-sum(c.duration for c in cuts)
                validated=validate_captions(cues,duration,width)
                self.caption_cues=validated;self.caption_signature=signature;self.caption_enabled=enabled.get()
                self.status.set(f'Altyazı {"açık" if self.caption_enabled else "kapalı"} · {len(validated)} satır. CapCut kopyası oluşturabilirsiniz.')
                self.update_buttons();dialog.destroy()
            except UserError as exc:messagebox.showerror('Altyazı kaydedilemedi',str(exc),parent=dialog)
        def disable():
            self.caption_enabled=False;self.update_buttons();self.status.set('Altyazı kapalı; kopyaya eklenmeyecek.');dialog.destroy()
        ttk.Button(row,text='Satırı güncelle',command=lambda:save_line()).pack(side='left')
        def save_line():
            try:commit()
            except UserError as exc:messagebox.showerror('Altyazı metni',str(exc),parent=dialog)
        ttk.Button(row,text='Kaydet ve kullan',style='Accent.TButton',command=save).pack(side='left',padx=8)
        ttk.Button(row,text='Altyazıyı kapat',command=disable).pack(side='right')
        table.selection_set('0');select()

    def job(self,kind,fn):
        if self.busy:return
        self.busy=True;self.cancel_event=threading.Event();self.progress.start(12);self.update_buttons()
        self.status.set('İşlem yapılıyor…')
        def work():
            try:self.events.put(('done',kind,fn()))
            except Exception as exc:self.events.put(('error',exc,traceback.format_exc()))
        threading.Thread(target=work,daemon=True).start()

    def start_analysis(self):
        if not self.project or self.busy:return
        try:
            settings=self.get_settings();settings.validate(self.project.duration)
            idx=self.tracks.current()
            if idx<0:raise UserError('Konuşma kaynağını seçin.')
            track=self.track_ids[idx]
            self.pending_track=track
            self.pending_settings=settings
            suggest=self.suggest_var.get();transcribe=self.transcribe_var.get() or suggest;project=self.project
            save_settings(settings,analysis_mode='smart',transcribe_text=transcribe,suggest_words=suggest)
            def run():
                return analyze_speech(project,track,settings,self.cancel_event,lambda msg:self.events.put(('status',msg)),transcribe=transcribe,suggest=transcribe and suggest)
            self.job('analysis',run)
        except Exception as exc:self.error(exc)

    def drain(self):
        self._drain_after=None
        try:
            while True:
                event=self.events.get_nowait()
                if event[0]=='status':self.status.set(event[1]);continue
                self.busy=False;self.progress.stop();self.progress['value']=0
                if self.closing:
                    self.finish_close();return
                if event[0]=='error':
                    if not isinstance(event[1],UserError):
                        (Path(self.temp.name)/'error.log').write_text(event[2],encoding='utf-8')
                    self.error(event[1])
                elif event[1]=='analysis':
                    self.analyzed_track=self.pending_track
                    result=event[2]
                    profile=result.context.get('jump_cut')
                    if profile and profile.get('version')=='direct-silence-v1':
                        self.jump_cut_status.set(f"Tüm zaman çizelgesi · Yeni konuşmadan önce {profile['word_onset_seconds']*1000:g} ms pay · Sessizlikler otomatik kesilir")
                    elif profile:
                        self.jump_cut_status.set(f"Tüm zaman çizelgesi · {profile['minimum_pause_seconds']:.2f} sn ve üzeri boşluklar · Konuşma arası yaklaşık {profile['retained_pause_seconds']:.2f} sn pay · Otomatik profil")
                    self.review_session=ReviewSession(self.project,self.pending_track,self.pending_settings,result.cuts,
                                                      proposals=result.proposals,context=result.context)
                    try:restored=self.review_session.restore()
                    except UserError as exc:self.error(exc);restored=False
                    self.cuts=self.review_session.cuts;self.enabled=self.review_session.enabled
                    self.populate();self.set_transcript(result.transcript);self.notebook.select(0)
                    if result.context.get('transcribe') and self.pending_settings.start==0 and self.pending_settings.end is None:
                        self.caption_words=copy.deepcopy(result.transcript)
                    self.status.set(('Kayıtlı kesimler geri yüklendi. ' if restored else '')+f'Analiz tamamlandı · {result.metrics.get("elapsed_seconds",0):.2f} sn · Tekrarlar işaretlenir; onay gerekmez.')
                    if self.issues:messagebox.showwarning('Proje uyumluluğu','Sessizlik analizi hazır; bu projeye güvenli yazma henüz desteklenmiyor:\n\n'+'\n'.join(self.issues))
                elif event[1]=='captions':
                    self.caption_words=copy.deepcopy(event[2].transcript)
                    self.set_transcript(self.caption_words)
                    self.prepare_captions_for_copy()
                elif event[1]=='preview':
                    self.audio.play(Path(event[2]))
                    self.status.set('Yalnızca seçilen konuşma kaynağı dinletiliyor. Müzik/diğer katmanlar önizlemeye dahil değil.')
                elif event[1]=='copy':
                    packet=event[2]
                    self.output=packet['path'] if isinstance(packet,dict) else packet
                    if isinstance(packet,dict):
                        self.caption_words=packet['words']
                        if self.caption_enabled:
                            self.caption_cues=packet['caption_cues'];self.caption_signature=self.current_caption_signature()
                    suffix=' · Altyazı zamanları otomatik güncellendi.' if isinstance(packet,dict) and packet['captions_refreshed'] else ''
                    self.status.set(f'Kopya hazır: {self.output}{suffix}')
                    messagebox.showinfo('Kopya oluşturuldu',f'Orijinal proje korundu.\n\n{self.output}\n\nCapCut’ı açın: “{self.project.name} · Sessizlik temizlendi” projesini kontrol edin.\nİlk kullanımda kısa bir dışa aktarımla senkronu doğrulayın.')
                    open_folder(Path(self.output))
                self.update_buttons()
        except queue.Empty:pass
        except Exception as exc:
            self.busy=False;self.progress.stop();self.progress['value']=0
            if event[0]=='done' and event[1]=='analysis':self.invalidate()
            self.error(exc);self.update_buttons()
        self._drain_after=self.after(80,self.drain)

    def set_transcript(self,words):
        self.transcript_selection_data=None;self.transcript_ranges=[];self.transcript_lines=[]
        self.transcript_status.set('Cümleye tıkla veya metinden bir bölüm seç.')
        self.transcript.configure(state='normal');self.transcript.delete('1.0','end')
        for sentence in transcript_sentences(words) if isinstance(words,list) else []:
            line_start=self.transcript.index('end-1c')
            self.transcript.insert('end',f'[{clock(sentence["start"])} – {clock(sentence["end"])}] ','timestamp')
            line_words=[]
            for word in sentence['words']:
                if line_words:self.transcript.insert('end',' ')
                start=self.transcript.index('end-1c')
                self.transcript.insert('end',word['word'].strip())
                item={'first':start,'last':self.transcript.index('end-1c'),**word}
                self.transcript_ranges.append(item);line_words.append(item)
            self.transcript_lines.append({'first':line_start,'last':self.transcript.index('end-1c'),'words':line_words})
            self.transcript.insert('end','\n')
        if not self.transcript_ranges:
            self.transcript.insert('1.0','Metinden bölüm çıkarmak için “Türkçe metin çıkar” seçeneğini işaretleyip Jump cut analiz et düğmesine basın.')
        self.transcript.configure(state='disabled')
        self.update_buttons()

    def select_transcript(self,event=None):
        if self.busy:return
        chosen=[]
        selection=self.transcript.tag_ranges('sel')
        if selection:
            first,last=selection
            chosen=[w for w in self.transcript_ranges if self.transcript.compare(w['last'],'>',first) and self.transcript.compare(w['first'],'<',last)]
        elif event is not None and hasattr(event,'x') and event.type==tk.EventType.ButtonRelease:
            index=self.transcript.index(f'@{event.x},{event.y}')
            line=next((line for line in self.transcript_lines if self.transcript.compare(line['first'],'<=',index) and self.transcript.compare(index,'<=',line['last'])),None)
            if line:chosen=line['words']
        self.transcript.tag_remove('chosen','1.0','end')
        self.transcript_selection_data=None
        if chosen:
            start=min(w['start'] for w in chosen);end=max(w['end'] for w in chosen)
            self.transcript_selection_data=(Cut(start,end),' '.join(w['word'].strip() for w in chosen))
            self.transcript.tag_add('chosen',chosen[0]['first'],chosen[-1]['last'])
            self.transcript_status.set(f'{clock(start)} – {clock(end)} · {(end-start)/US:.2f} sn')
        else:self.transcript_status.set('Cümleye tıkla veya metinden bir bölüm seç.')
        self.update_buttons()

    def listen_transcript(self):
        if self.busy or not self.transcript_selection_data or self.analyzed_track is None:return
        self.listen_range(self.transcript_selection_data[0],full=True)

    def cut_transcript(self):
        if self.busy or not self.review_session or not self.transcript_selection_data:return
        cut,text=self.transcript_selection_data
        try:
            i=self.review_session.add_manual(cut.start,cut.end,text)
            self.cuts=self.review_session.cuts;self.enabled=self.review_session.enabled
            self.populate();self.save_review(i)
            self.status.set('Metin seçimi kesimlere eklendi. Geri almak için Kesimleri kontrol et sekmesinde “Bu aralığı koru” seçin.')
        except (UserError,OSError) as exc:self.error(exc)

    def row_values(self,i,number=None):
        c=self.cuts[i];candidate=self.review_session.candidates[i];decision=self.review_session.decisions[i]
        kind={'silence':'Sessizlik','retake':'Tekrar işareti','manual':'Metinden seçim'}[candidate['kind']]
        label={'correct':'Otomatik · kes','wrong':'Koru','marker':'İşaret · kesilmez'}[decision]
        tag='proposal' if decision=='marker' else decision
        if number is None:number=self.tree.index(str(i))+1
        return (number,kind,label,clock(c.start),clock(c.end),f'{c.duration/US:.2f} sn'),(tag,)

    def populate(self):
        selected=self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        for number,i in enumerate(sorted(range(len(self.cuts)),key=lambda n:(self.cuts[n].start,self.cuts[n].end)),1):
            values,tags=self.row_values(i,number)
            self.tree.insert('', 'end',iid=str(i),tags=tags,values=values)
        if self.cuts:
            row=selected[0] if selected and self.tree.exists(selected[0]) else '0'
            self.tree.selection_set(row);self.tree.focus(row);self.tree.see(row)
        self.update_summary();self.draw();self.selection_changed()

    def update_metrics(self):
        if not hasattr(self,'metric_vars'):return
        total=self.project.duration if self.project else None
        removed=0
        if self.review_session:
            try:removed=sum(c.duration for c in self.review_session.selected_cuts())
            except UserError:pass
        values=(clock(total),clock(removed),clock(max(0,total-removed))) if total is not None else ('—','—','—')
        for var,value in zip(self.metric_vars,values):var.set(value)

    def update_summary(self):
        if not self.project or not self.review_session:return
        try:
            removed=sum(c.duration for c in self.review_session.selected_cuts());self.export_error=None
        except UserError as exc:
            removed=0;self.export_error=str(exc)
        markers=sum(c.get('marker_only',False) for c in self.review_session.candidates)
        self.update_metrics()
        self.summary.set(self.export_error or f'{len(self.enabled)} otomatik kesim · {markers} tekrar işareti · Kazanç: {removed/US:.2f} sn · Yeni süre: {clock(self.project.duration-removed)}')
        self.update_buttons()

    def selection_changed(self):
        rows=self.tree.selection()
        if rows and self.review_session:
            candidate=self.review_session.candidates[int(rows[0])];text=candidate.get('text','')
            if candidate.get('comparison'):text+=' → Sonraki okuma: '+candidate['comparison']
            limit=100 if self.winfo_height()<800 else 450
            self.detail.set(text[:limit] or 'Sessizlik / konuşma dışı aralık')
        else:self.detail.set('Sessizlikler otomatik kesilir. Tekrarlar yalnızca işaretlenir; onay gerekmez.')
        self.update_buttons()

    def draw(self):
        if not hasattr(self,'canvas'):return
        self.canvas.delete('all')
        if not self.project:return
        w=max(1,self.canvas.winfo_width());dur=self.project.duration
        self.canvas.create_rectangle(0,12,w,31,fill='#28352f',outline='')
        for i,c in enumerate(self.cuts):
            marker=self.review_session and self.review_session.candidates[i].get('marker_only')
            color='#40d9b0' if i in self.enabled else ('#bfc9c3' if marker else '#57635d')
            self.canvas.create_rectangle(c.start/dur*w,12,c.end/dur*w,31,fill=color,outline='')
        self.canvas.create_text(5,3,text='0:00',fill='#8e9c96',anchor='nw',font=('Segoe UI',8))
        self.canvas.create_text(w-5,3,text=clock(dur),fill='#8e9c96',anchor='ne',font=('Segoe UI',8))

    def toggle_selected(self):
        rows=self.tree.selection()
        if rows:self.toggle(int(rows[0]))

    def toggle(self,i):
        if self.busy or not self.review_session:return
        state=self.review_session.decisions[i]
        self.review_session.mark(i,'wrong' if state=='correct' else 'correct')
        self.save_review(i)

    def save_review(self,i):
        self.cuts=self.review_session.cuts;self.enabled=self.review_session.enabled
        if self.tree.exists(str(i)):
            values,tags=self.row_values(i);self.tree.item(str(i),values=values,tags=tags)
            self.tree.selection_set(str(i));self.tree.focus(str(i));self.tree.see(str(i))
        self.update_summary();self.draw();self.selection_changed()
        try:
            self.review_session.save()
            self.status.set('Karar yerelde kaydedildi. Aynı projeyi aynı ayarlarla analiz ettiğinde geri yüklenir.')
        except (OSError,UserError) as exc:self.error(exc)

    def mark_selected(self,state):
        rows=self.tree.selection()
        if self.busy or not self.review_session or not rows:return
        i=int(rows[0]);self.review_session.mark(i,state);self.save_review(i)

    def next_cut(self):
        selected=self.tree.selection();rows=self.tree.get_children()
        if self.busy or not rows:return
        i=min(len(rows)-1,rows.index(selected[0])+1) if selected and selected[0] in rows else 0
        self.tree.selection_set(rows[i]);self.tree.focus(rows[i]);self.tree.see(rows[i]);self.tree.focus_set()


    def edit_selected(self):
        rows=self.tree.selection()
        if self.busy or not self.review_session or not rows:return
        i=int(rows[0]);cut=self.cuts[i]
        dialog=tk.Toplevel(self);dialog.title(f'{self.tree.index(rows[0])+1}. kesimi düzelt');dialog.transient(self);dialog.grab_set();dialog.resizable(False,False)
        box=ttk.Frame(dialog,padding=20);box.pack(fill='both',expand=True)
        ttk.Label(box,text='Yeni sınırları saniye veya SS:DD:SN biçiminde yaz.').pack(anchor='w',pady=(0,12))
        values=[]
        for label,value in [('Başlangıç',cut.start),('Bitiş',cut.end)]:
            ttk.Label(box,text=label).pack(anchor='w')
            var=tk.StringVar(value=f'{value/US:.6f}')
            entry=ttk.Entry(box,textvariable=var,width=36);entry.pack(fill='x',pady=(4,12));values.append(var)
        def apply():
            try:
                a,b=[seconds(var.get()) for var in values]
                self.review_session.edit(i,round(a*US),round(b*US))
                self.save_review(i);dialog.destroy()
            except (ValueError,OverflowError,UserError) as exc:messagebox.showerror('Aralık uygulanamadı',str(exc),parent=dialog)
        ttk.Label(box,text='Sınırlar tam kareye içeri yuvarlanır. Kaydedilen aralık kesime dahil edilir.',wraplength=390,style='Sub.TLabel').pack(anchor='w',pady=(0,10))
        ttk.Button(box,text='Kesim sınırını kaydet',command=apply).pack(fill='x')
        dialog.bind('<Return>',lambda _:apply())

    def listen(self,after):
        rows=self.tree.selection()
        if self.busy or not rows or self.analyzed_track is None:return
        cut=self.cuts[int(rows[0])]
        self.listen_range(cut,after=after)

    def listen_range(self,cut,after=False,full=False):
        if cut.duration>10*US:
            if not full:self.status.set('Uzun sessizlikte iki kesim sınırının çevresi dinletilir; ortadaki uzun bölüm atlanır.')
        project=self.project;track=self.analyzed_track
        key=hashlib.sha256(f'{project.hashes[project.file]}:{track}:{cut}:{after}:{full}'.encode()).hexdigest()
        output=Path(self.temp.name)/(key+'.wav')
        self.audio.stop()
        def render():
            project.assert_unchanged()
            if not output.exists():
                temp=output.with_suffix('.tmp.wav')
                try:
                    preview(project,track,cut,temp,self.cancel_event,after,full=full);os.replace(temp,output)
                finally:temp.unlink(missing_ok=True)
            return output
        self.job('preview',render)

    def write_copy(self):
        if not self.project or self.busy:return
        if self.issues:
            messagebox.showwarning('Desteklenmeyen yapılar','\n'.join(self.issues));return
        try:cuts=self.review_session.selected_cuts() if self.review_session else []
        except UserError as exc:self.error(exc);return
        audit=self.review_session.payload() if self.review_session else None
        project=self.project;track=self.track_ids[self.tracks.current()]
        caption_enabled=self.caption_enabled;current=self.captions_ready();mark_repeats=self.suggest_var.get()
        words=copy.deepcopy(self.caption_words);cues=copy.deepcopy(self.caption_cues)
        proposals=[dict(c,start=self.review_session.cuts[i].start,end=self.review_session.cuts[i].end)
                   for i,c in enumerate(self.review_session.candidates) if c.get('marker_only')] if self.review_session else []
        if not self.review_session or not self.review_session.identity.get('analysis_context',{}).get('suggest'):
            proposals=None
        self.job('copy',lambda:export_copy(project,track,cuts,self.cancel_event,lambda msg:self.events.put(('status',msg)),
            caption_enabled=caption_enabled,captions_current=current,caption_words=words,caption_cues=cues,
            mark_repeats=mark_repeats,proposals=proposals,review=audit))

    def update_buttons(self):
        if not hasattr(self,'copy_btn'):return
        self.analyze_btn['state']='normal' if self.project and self.track_ids and not self.busy else 'disabled'
        ready=self.captions_ready()
        copy_primary=bool(self.review_session or self.caption_enabled or ready)
        self.analyze_btn.configure(style='TButton' if copy_primary else 'Accent.TButton')
        self.copy_btn.configure(style='Accent.TButton' if copy_primary else 'TButton')
        self.copy_btn['state']='normal' if self.project and self.track_ids and (self.review_session or self.caption_enabled or ready) and not self.busy else 'disabled'
        self.caption_btn['state']='normal' if self.project and self.track_ids and not self.busy else 'disabled'
        self.caption_btn['text']=('Altyazı ✓' if ready else 'Altyazı · otomatik') if self.caption_enabled else 'Otomatik altyazı'
        self.caption_toggle_var.set(self.caption_enabled)
        self.caption_toggle['state']='normal' if self.project and not self.busy else 'disabled'
        for btn in (self.listen_btn,self.after_btn):btn['state']='normal' if self.cuts and not self.busy else 'disabled'
        for btn in (self.refresh_btn,self.browse_btn):btn['state']='disabled' if self.busy else 'normal'
        self.transcribe_check['state']='normal' if not self.busy else 'disabled'
        self.suggest_check['state']='normal' if not self.busy else 'disabled'
        for btn in (self.transcript_listen_btn,self.transcript_cut_btn):
            btn['state']='normal' if self.transcript_selection_data and self.review_session and self.analyzed_track is not None and not self.busy else 'disabled'
        for btn in (self.correct_btn,self.wrong_btn,self.edit_btn,self.next_btn):
            btn['state']='normal' if self.review_session and self.tree.selection() and not self.busy else 'disabled'
        selected=self.tree.selection()
        if self.review_session and selected and self.review_session.candidates[int(selected[0])].get('marker_only'):
            for btn in (self.correct_btn,self.wrong_btn,self.edit_btn,self.after_btn):btn['state']='disabled'
        self.projects['state']='disabled' if self.busy else 'readonly';self.tracks['state']='disabled' if self.busy else 'readonly'
        self.cancel_btn['state']='normal' if self.busy else 'disabled'

    def error(self,exc):
        self.status.set(str(exc).split('\n')[0])
        if not isinstance(exc,Cancelled):messagebox.showerror('İşlem tamamlanamadı',str(exc))

    def close(self):
        if self.busy:
            self.closing=True;self.cancel_event.set();self.status.set('İşlem durduruluyor…');return
        self.finish_close()

    def finish_close(self):
        pending=getattr(self,'_drain_after',None)
        if pending:
            self.after_cancel(pending);self._drain_after=None
        self.audio.stop();self.temp.cleanup();self.update_idletasks();self.destroy()


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Yerel CapCut sessizlik temizleyici')
    parser.add_argument('--project',type=Path,help='CapCut proje klasörü')
    App(parser.parse_args().project).mainloop()


