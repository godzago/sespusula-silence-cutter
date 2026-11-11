"""Point markers for possible repeated takes; markers never become deletion ranges."""
from bisect import bisect_right
import copy

from silence_core import US, UserError, normalize_cuts, uid


def validate_time_marks(value, duration):
    if value is None:return
    if not isinstance(value,dict) or not isinstance(value.get('mark_items'),list):
        raise UserError('Zaman işareti biçimi tanınmadı.')
    for item in value['mark_items']:
        span=item.get('time_range') if isinstance(item,dict) else None
        if (not isinstance(span,dict) or type(span.get('start')) is not int or type(span.get('duration')) is not int or
            not 0<=span['start']<=duration or not 0<=span['duration']<=duration-span['start'] or
            not isinstance(item.get('title',''),str)):
            raise UserError('Zaman işareti aralığı geçersiz.')


def time_mapper(cuts,duration):
    cuts=normalize_cuts(cuts,duration);ends=[c.end for c in cuts];prefix=[0]
    for c in cuts:prefix.append(prefix[-1]+c.duration)
    def mapped(value):
        i=bisect_right(ends,value)
        return value-prefix[i]-(max(0,value-cuts[i].start) if i<len(cuts) else 0)
    return cuts,mapped


def remap_time_marks(value,cuts,duration):
    validate_time_marks(value,duration)
    if value is None:return None
    cuts,mapped=time_mapper(cuts,duration);ends=[c.end for c in cuts];result=copy.deepcopy(value);items=[]
    for item in result['mark_items']:
        a=item['time_range']['start'];b=a+item['time_range']['duration']
        index=bisect_right(ends,a)
        if a==b and index<len(cuts) and cuts[index].start<=a:continue
        x,y=mapped(a),mapped(b)
        if b>a and y<=x:continue
        item['time_range']={'start':x,'duration':y-x};items.append(item)
    result['mark_items']=items
    return result


def repeat_markers(proposals):
    result=[];seen=set()
    for p in proposals:
        if p.get('kind')!='retake':continue
        pairs=[(p['start'],p['end'],p.get('text',''))]
        if type(p.get('comparison_start')) is int and type(p.get('comparison_end')) is int:
            pairs.append((p['comparison_start'],p['comparison_end'],p.get('comparison','')))
        for a,b,text in pairs:
            if (a,b) in seen:continue
            seen.add((a,b));text=' '.join(text.split())
            result.append({'start':a,'end':b,'title':'Tekrar olabilir · '+text[:80],
                           'text':text,'score':p.get('score'),'color':'#F4B942'})
    return sorted(result,key=lambda m:(m['start'],m['end']))


def add_repeat_markers(data,markers,cuts,source_duration):
    if not markers:return []
    validate_time_marks(data.get('time_marks'),data['duration'])
    if data.get('time_marks') is None:data['time_marks']={'id':uid(),'mark_items':[]}
    cuts,mapped=time_mapper(cuts,source_duration);ends=[c.end for c in cuts];report=[]
    existing={(m.get('title',''),m['time_range']['start']) for m in data['time_marks']['mark_items']
              if m['time_range']['duration']==0}
    for marker in markers:
        a,b=marker.get('start'),marker.get('end')
        if type(a) is not int or type(b) is not int or not 0<=a<b<=source_duration:
            raise UserError('Tekrar işaretinin kaynak aralığı geçersiz.')
        index=bisect_right(ends,a)
        cursor=cuts[index].end if index<len(cuts) and cuts[index].start<=a else a
        if cursor>=b:continue
        t=mapped(cursor)
        if not 0<=t<data['duration']:continue
        title=str(marker.get('title','Tekrar olabilir'))
        if (title,t) in existing:continue
        existing.add((title,t))
        data['time_marks']['mark_items'].append({'id':uid(),'title':title,
            'color':marker.get('color','#F4B942'),'time_range':{'start':t,'duration':0}})
        report.append({**marker,'output_start_us':t,'source_start_us':a,'source_end_us':b})
    data['time_marks']['mark_items'].sort(key=lambda m:m['time_range']['start'])
    return report
