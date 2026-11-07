from pathlib import Path
import shutil
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT=Path(__file__).resolve().parents[2]
path=ROOT/'report/LumaRestore_Technical_Solution_Report.docx'
backup=ROOT/'tmp/report/report_before_network_update.docx'
if not backup.exists():shutil.copy2(path,backup)
doc=Document(backup)
heading=next(p for p in doc.paragraphs if p.text=='2 2 Deep Learning Pipeline')
hybrid=next(p for p in doc.paragraphs if p.text=='2 3 Hybrid Integration and Adaptive Mechanism')
node=heading._p.getnext()
while node is not hybrid._p:
    nxt=node.getnext();node.getparent().remove(node);node=nxt
heading.paragraph_format.page_break_before=True

def para(text,style=None):return hybrid.insert_paragraph_before(text,style)
para('Model architecture  The neural branch uses the official pretrained Retinexformer LOL-v1 model in PyTorch. It combines an illumination estimator with an illumination-guided transformer restoration module. The project reuses the published architecture and checkpoint; it does not introduce a new neural network. See backend/src/deep/inference.py and backend/src/deep/vendor/retinexformer_arch.py. [R1, R2]')
para('Illumination estimator  The three-channel RGB input is concatenated with its channel-wise mean to form a four-channel representation. A 1 by 1 convolution projects this into 40 channels, followed by a grouped 5 by 5 convolution. A final 1 by 1 convolution predicts a three-channel illumination map. The adjusted input is input multiplied by the illumination map plus input. The estimator also supplies illumination features to guide restoration.')
para('Restoration network  A 3 by 3 input convolution feeds a two-level encoder with feature widths of 40, 80 and 160 channels. Illumination-guided attention blocks operate at the encoder scales and bottleneck. The decoder restores resolution using transposed convolutions, encoder skip connections and further attention blocks. A final 3 by 3 convolution predicts an RGB residual that is added to the illumination-adjusted input.')
para('Neural network specifications','Heading 3')
rows=[
('Framework and model','PyTorch; single-stage Retinexformer'),
('Input and output','Three-channel RGB; inference input and clipped output in [0, 1]'),
('Restoration stages','1'),
('Feature widths','40, 80 and 160 channels across scales'),
('Encoder and decoder','2 downsampling levels; 2 matching upsampling levels'),
('Attention block configuration','[1, 2, 2] for encoder scales and bottleneck; mirrored decoder'),
('Total block pairs','8 attention and feed-forward pairs across the full restoration module'),
('Attention heads','1, 2 and 4 at the 40, 80 and 160 channel scales'),
('Dimension per attention head','40'),
('Feed-forward module','Expansion factor 4; GELU; depthwise 3 by 3 convolution'),
('Downsampling and upsampling','4 by 4 stride-2 convolutions; 2 by 2 stride-2 transposed convolutions'),
('Reconstruction connections','Encoder skip connections and residual RGB output'),
('Total parameters','1,605,701; counted from the instantiated project model'),
('FP32 parameter storage','Approximately 6.13 MiB; excludes activations and runtime overhead'),
('Production checkpoint','Official pretrained LOL-v1 weights'),
]
t=doc.add_table(rows=1,cols=2);t.autofit=False
t.columns[0].width=Inches(2.15);t.columns[1].width=Inches(4.72)
t.rows[0].cells[0].text='Specification';t.rows[0].cells[1].text='Project configuration'
for a,b in rows:
    c=t.add_row().cells;c[0].text=a;c[1].text=b
for ri,row in enumerate(t.rows):
    pr=row._tr.get_or_add_trPr();cs=OxmlElement('w:cantSplit');pr.append(cs)
    if ri==0:pr.append(OxmlElement('w:tblHeader'))
    for ci,c in enumerate(row.cells):
        c.width=Inches(2.15 if ci==0 else 4.72);c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
        prop=c._tc.get_or_add_tcPr()
        sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'233B50' if ri==0 else ('F3F6F8' if ri%2 else 'FFFFFF'));prop.append(sh)
        margins=OxmlElement('w:tcMar')
        for side in ['top','left','bottom','right']:
            e=OxmlElement('w:'+side);e.set(qn('w:w'),'65');e.set(qn('w:type'),'dxa');margins.append(e)
        prop.append(margins)
        for p in c.paragraphs:
            p.paragraph_format.space_after=Pt(0);p.paragraph_format.line_spacing=1
            for r in p.runs:r.font.size=Pt(9);r.font.bold=(ri==0);r.font.color.rgb=RGBColor.from_string('FFFFFF' if ri==0 else '000000')
borders=OxmlElement('w:tblBorders')
for side in ['top','left','bottom','right','insideH','insideV']:
    e=OxmlElement('w:'+side);e.set(qn('w:val'),'single');e.set(qn('w:sz'),'4');e.set(qn('w:color'),'D9D9D9');borders.append(e)
t._tbl.tblPr.append(borders)
hybrid._p.addprevious(t._tbl)
para('The parameter count and storage estimate describe this instantiated configuration. They do not measure inference memory or include checkpoint metadata.','Caption')

start=para('Deep Learning Inference and Training','Heading 2');start.paragraph_format.page_break_before=True
para('Inference implementation  The engine validates checkpoint weights strictly, caches one loaded model and runs in inference mode. Inputs are padded to multiples of eight. Larger images use overlapping tiles with weighted reconstruction to reduce boundary artifacts. The benchmark tile limit was 1024 pixels with 32-pixel overlap; all 600 by 400 test images fitted within one tile. CPU execution is supported, with CUDA when compatible hardware is available and recovery to CPU for supported device failures. Deep-only mode processes original RGB independently of classical enhancement and fusion.')
para('Dataset protocol  The preparation script splits the official 485-pair LOL-v1 training partition into 437 training and 48 development pairs with seed 42. The 15 official test pairs remain separate. Development images may have appeared in the official checkpoint\'s upstream training corpus, so they do not establish unseen pretraining generalization. Test references enter evaluation only and never guide restoration. [R3, R4]')
para('Loss functions and training  An exploratory supervised fine-tuning run used one epoch on CPU, 64 by 64 patches, batch size 2 and Adam at learning rate 0.0003. The adaptation loss combines mean Charbonnier reconstruction error with horizontal and vertical gradient L1 errors: loss = mean(sqrt((prediction - reference) squared + 0.000001)) + 0.05 times (horizontal gradient L1 + vertical gradient L1). This is the local adaptation objective, not a reproduction of the original model\'s training recipe. The script includes gradient clipping, a cosine learning-rate scheduler, development validation and checkpoint saving. [R5]')
para('Measured adaptation outcome  Recorded training and development losses were 0.09063 and 0.10235. On the official test set, adaptation reduced PSNR from 25.1553 to 21.5054 dB and SSIM from 0.8441 to 0.8132. The adapted checkpoint was not deployed; the application retains the original pretrained weights. NIQE improved slightly despite worse reference metrics, illustrating why NIQE alone is insufficient for model promotion. The test set was excluded from fine-tuning updates.')

# Dataset and adaptation details now belong to Section 2.2; remove the older duplicate subsection.
old=next(p for p in doc.paragraphs if p.text=='Training and dataset use')
frontend=next(p for p in doc.paragraphs if p.text=='Frontend and processing outputs')
node=old._p
while node is not frontend._p:
    nxt=node.getnext();node.getparent().remove(node);node=nxt
hybrid.paragraph_format.page_break_before=True
doc.save(path)
print('Updated neural architecture, specifications, inference and training in Section 2.2.')
