from pathlib import Path
import shutil
from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

ROOT=Path(__file__).resolve().parents[2]
REPORT=ROOT/'report/LumaRestore_Technical_Solution_Report.docx'
TMP=ROOT/'tmp/report'
if not (TMP/'report_before_architecture.docx').exists():
    shutil.copy2(REPORT,TMP/'report_before_architecture.docx')

im=Image.new('RGB',(1800,1700),'white')
d=ImageDraw.Draw(im)
ink='#233B50'; line='#526B7A'
bold=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf',36)
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',32)
small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',30)

def box(rect,title,lines,fill='#F1F5F8'):
    d.rounded_rectangle(rect,radius=18,fill=fill,outline=ink,width=3)
    x=(rect[0]+rect[2])/2
    total=44+len(lines)*40
    y=(rect[1]+rect[3]-total)/2
    d.text((x,y),title,font=bold,fill='black',anchor='mt')
    for i,t in enumerate(lines):d.text((x,y+49+i*40),t,font=font,fill='black',anchor='mt')

def arrow(points,color=line,width=5):
    d.line(points,fill=color,width=width,joint='curve')
    x,y=points[-1];px,py=points[-2]
    if y>py:head=[(x,y),(x-12,y-20),(x+12,y-20)]
    elif y<py:head=[(x,y),(x-12,y+20),(x+12,y+20)]
    elif x>px:head=[(x,y),(x-20,y-12),(x-20,y+12)]
    else:head=[(x,y),(x+20,y-12),(x+20,y+12)]
    d.polygon(head,fill=color)

box((300,15,1500,155),'React and TypeScript studio',[
    'Image upload and restoration mode selection',
    'Analysis, comparison, ablations and downloads'])
arrow([(900,155),(900,205)])
box((300,205,1500,350),'FastAPI backend',[
    'Validate upload, decode image and apply resource limits',
    'Normalize RGB and check reference dimensions'])
arrow([(900,350),(900,400)])
box((300,400,1500,555),'Image analysis and mode dispatch',[
    'Exposure, noise, texture, colour and illumination statistics',
    'Validated RGB goes to the requested processing branch'])
arrow([(475,555),(475,625)])
arrow([(1325,555),(1325,625)])
box((130,625,820,820),'Classical restoration',[
    'Guided illumination and bounded Retinex',
    'Adaptive denoising and CLAHE',
    'Colour and highlight safeguards'])
box((980,625,1670,820),'Pretrained Retinexformer',[
    'Official LOL-v1 checkpoint',
    'Independent neural inference',
    'CPU or CUDA and overlapping tiles'])
arrow([(600,820),(600,900)])
arrow([(1200,820),(1200,900)])
d.text((900,853),'Hybrid path uses both candidates',font=small,fill=ink,anchor='mm')
box((360,900,1440,1095),'Adaptive hybrid controller',[
    'Local candidate confidence and guided spatial fusion',
    'Highlight protection, artifact checks and candidate selection',
    'Statistics guide fusion outside the neural network'])
arrow([(900,1095),(900,1175)])
box((360,1175,1440,1320),'Selected restoration output',[
    'Classical, deep or controller-selected candidate',
    'Optional vivid finish and interpolated 4K export'])
arrow([(130,723),(65,723),(65,1248),(360,1248)])
arrow([(1670,723),(1735,723),(1735,1248),(1440,1248)])

def vertical_label(text,x):
    label=Image.new('RGBA',(650,46),(255,255,255,0))
    ImageDraw.Draw(label).text((325,23),text,font=small,fill=ink,anchor='mm')
    label=label.rotate(90,expand=True)
    im.paste(label,(x,680),label)
vertical_label('Classical mode bypasses fusion',78)
vertical_label('Deep mode bypasses fusion',1680)
arrow([(900,1320),(900,1390)])
box((250,1390,1550,1550),'Evaluation, storage and frontend results',[
    'PSNR, SSIM and LPIPS with aligned reference; NIQE without reference',
    'Diagnostics, stage maps, PNG exports and CSV / JSON / ZIP reports'])
d.text((900,1605),'Auto mode chooses classical or runs the hybrid path using exposure and model availability.',font=small,fill='black',anchor='mm')
d.text((900,1650),'The reference is used for evaluation only and never guides restoration.',font=small,fill='black',anchor='mm')
diagram=TMP/'architecture_diagram.png'
im.save(diagram)

doc=Document(TMP/'report_before_architecture.docx')
assert not any('Figure 1  LumaRestore architecture' in p.text for p in doc.paragraphs)
# Advance existing figure captions before adding the architecture as Figure 1.
for para in doc.paragraphs:
    for n in [4,3,2,1]:
        prefix=f'Figure {n}  '
        if para.text.startswith(prefix):
            for run in para.runs:
                if run.text.startswith(prefix):run.text=run.text.replace(prefix,f'Figure {n+1}  ',1);break
            else:para.text=para.text.replace(prefix,f'Figure {n+1}  ',1)
            break
target=next(p for p in doc.paragraphs if p.text=='2 1 Classical Algorithmic Baseline')
pic=target.insert_paragraph_before()
pic.alignment=WD_ALIGN_PARAGRAPH.CENTER
pic.add_run().add_picture(str(diagram),width=Inches(6.87))
pic._p.xpath('.//wp:docPr')[0].set('descr','LumaRestore architecture showing frontend, API, image analysis, independent classical and neural branches, hybrid fusion, direct mode bypasses and evaluation outputs')
cap=target.insert_paragraph_before('Figure 1  LumaRestore architecture and restoration data flow',style='Caption')
cap.paragraph_format.keep_with_next=True
note=target.insert_paragraph_before('Classical and deep modes return their own restoration candidates directly. Hybrid mode computes both candidates before fusion and selection; automatic mode chooses a path using exposure severity and model availability. The diagram summarizes backend/app/service.py and the branch modules in [R1].')
target.paragraph_format.page_break_before=True
doc.save(REPORT)
print('Added architecture diagram to',REPORT)
