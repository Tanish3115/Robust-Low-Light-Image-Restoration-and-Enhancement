from pathlib import Path
import json
from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[2]
TMP = ROOT / 'tmp/report'
OUT = ROOT / 'output/reports'
DATA = json.loads((TMP / 'evidence.json').read_text(encoding='utf-8'))
BENCH = DATA['benchmark']['averages']
ABL = DATA['ablation']['averages']
REPO = 'https://github.com/Tanish3115/Robust-Low-Light-Image-Restoration-and-Enhancement'
FONT = 'C:/Windows/Fonts/arial.ttf'

def figure_grid(name, panels, columns=4, panel_width=600):
    rows = (len(panels) + columns - 1) // columns
    ph = 400
    header = 50
    gap = 16
    canvas = Image.new('RGB', (columns*panel_width+(columns-1)*gap, rows*(ph+header)+(rows-1)*gap), 'white')
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(FONT, 38 if columns == 4 else 27)
    for i, (label, path) in enumerate(panels):
        x=(i%columns)*(panel_width+gap); y=(i//columns)*(ph+header+gap)
        draw.text((x+3,y+9),label,font=font,fill='black')
        image=Image.open(path).convert('RGB')
        image.thumbnail((panel_width,ph),Image.Resampling.LANCZOS)
        canvas.paste(image,(x+(panel_width-image.width)//2,y+header+(ph-image.height)//2))
    path=TMP/f'{name}.png'; canvas.save(path); return path

def comparison(key,name):
    ex=DATA['examples'][key]; base=ROOT/f"outputs/LOL-v1-final-benchmark/{ex['index']:05d}"
    return figure_grid(name,[('Low light input',base/'original.png'),('Deep only',base/'deep.png'),
                             ('Adaptive hybrid',base/'hybrid.png'),('Normal light reference',ex['reference'])])

extreme=comparison('493','figure_extreme')
backlit=comparison('780','figure_nonuniform')
failure=comparison('79','figure_failure')
maps=figure_grid('figure_maps',[
    ('Low light input',DATA['examples']['493']['input']),
    ('Maximum RGB illumination',TMP/'illumination_original.png'),
    ('Guided illumination',TMP/'illumination_refined.png'),
    ('Reflectance estimate',TMP/'reflectance.png'),
    ('Canny edge map',TMP/'edge_map.png'),
    ('Classical output',ROOT/'outputs/LOL-v1-final-benchmark/00006/classical.png')],columns=2)

doc=Document()
sec=doc.sections[0]
sec.page_width=Inches(8.27);sec.page_height=Inches(11.69)
sec.top_margin=Inches(.68);sec.bottom_margin=Inches(.68)
sec.left_margin=Inches(.7);sec.right_margin=Inches(.7)
sec.header_distance=Inches(.25);sec.footer_distance=Inches(.3)
styles=doc.styles
for style in styles:
    for border in style.element.xpath('.//w:pBdr'):
        border.getparent().remove(border)
for name in ['Normal','Body Text','Title','Subtitle','Heading 1','Heading 2','Heading 3','Caption']:
    styles[name].font.name='Arial'
    styles[name].font.color.rgb=RGBColor(0,0,0)
normal=styles['Normal'];normal.font.size=Pt(10.5)
normal.paragraph_format.space_after=Pt(7)
normal.paragraph_format.line_spacing=1.10
for name,size in [('Title',26),('Subtitle',13),('Heading 1',17),('Heading 2',12.5),('Heading 3',11)]:
    styles[name].font.size=Pt(size)
    styles[name].paragraph_format.space_before=Pt(13 if name!='Title' else 0)
    styles[name].paragraph_format.space_after=Pt(7)
    styles[name].paragraph_format.keep_with_next=True
styles['Caption'].font.size=Pt(9)
styles['Caption'].font.italic=False
styles['Subtitle'].font.italic=False
styles['Caption'].paragraph_format.space_after=Pt(8)
code_style=styles.add_style('Report Code',1)
code_style.font.name='Consolas';code_style.font.size=Pt(8)
code_style.paragraph_format.space_after=Pt(0)
code_style.paragraph_format.line_spacing=1
footer=sec.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.RIGHT
run=footer.add_run('LumaRestore AI  |  ');run.font.size=Pt(8);run.font.color.rgb=RGBColor.from_string('555555')
field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');footer._p.append(field)
doc.core_properties.title='LumaRestore AI Hackathon Technical Solution Report'
doc.core_properties.subject='Low light image restoration implementation and measured evaluation'
doc.core_properties.author=''
doc.core_properties.keywords='LumaRestore, Retinexformer, LOL-v1, ablation study'

def p(text='',style=None):return doc.add_paragraph(text,style)
def h(text,level=1):return doc.add_heading(text,level)
def page():doc.add_page_break()
def bullet(text):p(text,'List Bullet')
def image(path,width=6.87):
    para=doc.add_paragraph();para.alignment=WD_ALIGN_PARAGRAPH.CENTER
    para.paragraph_format.space_after=Pt(4)
    para.add_run().add_picture(str(path),width=Inches(width))
    pic=para._p.xpath('.//wp:docPr')
    if pic:pic[0].set('descr',Path(path).stem.replace('_',' '))
def caption(text):p(text,'Caption')
def table(headers,rows,widths):
    t=doc.add_table(rows=1,cols=len(headers));t.autofit=False;t.alignment=WD_TABLE_ALIGNMENT.CENTER
    for cell,w in zip(t.columns,widths):cell.width=Inches(w)
    tblpr=t._tbl.tblPr
    borders=OxmlElement('w:tblBorders')
    for edge in ['top','left','bottom','right','insideH','insideV']:
        e=OxmlElement(f'w:{edge}');e.set(qn('w:val'),'single');e.set(qn('w:sz'),'4');e.set(qn('w:color'),'D9D9D9');borders.append(e)
    tblpr.append(borders)
    for i,label in enumerate(headers):t.rows[0].cells[i].text=label
    repeat=OxmlElement('w:tblHeader');t.rows[0]._tr.get_or_add_trPr().append(repeat)
    for row in rows:
        cells=t.add_row().cells
        for cell,value in zip(cells,row):cell.text=str(value)
    for ri,row in enumerate(t.rows):
        cant=OxmlElement('w:cantSplit');row._tr.get_or_add_trPr().append(cant)
        for ci,cell in enumerate(row.cells):
            cell.width=Inches(widths[ci]);cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            tcpr=cell._tc.get_or_add_tcPr();shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'233B50' if ri==0 else ('F3F6F8' if ri%2 else 'FFFFFF'));tcpr.append(shade)
            margins=OxmlElement('w:tcMar')
            for side in ['top','left','bottom','right']:
                e=OxmlElement(f'w:{side}');e.set(qn('w:w'),'85');e.set(qn('w:type'),'dxa');margins.append(e)
            tcpr.append(margins)
            for para in cell.paragraphs:
                para.paragraph_format.space_after=Pt(0);para.paragraph_format.line_spacing=1.05
                para.alignment=WD_ALIGN_PARAGRAPH.LEFT if ci==0 else WD_ALIGN_PARAGRAPH.CENTER
                for r in para.runs:
                    r.font.size=Pt(9);r.font.bold=(ri==0)
                    r.font.color.rgb=RGBColor.from_string('FFFFFF' if ri==0 else '000000')
    p('').paragraph_format.space_after=Pt(0)
    return t
def code(lines):
    for line in lines.splitlines():p(line,'Report Code')
    p('').paragraph_format.space_after=Pt(0)
def mean(method,metric):return BENCH[method][metric]['mean']

# Page 1
p('LumaRestore AI','Title')
p('Hackathon Technical Solution Report','Subtitle')
p('Adaptive low light image restoration with classical vision and a pretrained transformer')
table(['Field','Details'],[
 ('Problem ID','[Enter official problem ID]'),
 ('Problem title','[Enter exact official challenge title]'),
 ('Team name','[Enter registered team name]'),
 ('Team members','[Enter full names and roll numbers]'),
 ('GitHub repository',REPO),
 ('Current base commit','8a401715b1ec0bb292752aa44d4970fe4943ecf5'),
 ('Demo','Local app: http://127.0.0.1:5173\n[Add public demo or video link]'),
 ('Report date','7 November 2026'),
],[1.4,5.47])
h('1 Problem Understanding and Solution Strategy')
h('Core technical challenge',2)
p('Brightening a dark photograph also makes noise, compression and colour errors more visible. A single exposure adjustment is especially unreliable when the frame contains both deep shadows and bright windows or light sources. LumaRestore addresses uneven illumination, noise amplification, colour shifts and loss of fine structure while keeping the restoration process inspectable.')
p('The application runs locally on CPU and can use CUDA when compatible hardware is available. Uploads are bounded to 20 MB and 40 million input pixels by default, with a 2048-pixel processing long edge. These are resource controls rather than a real-time performance guarantee. The measured CPU deep inference time is about 2.25 seconds per 600 by 400 image, excluding browser and evaluation overhead.')
h('Proposed methodology',2)
p('We first measure exposure, noise, texture and illumination variation, then generate classical and neural restoration candidates independently. A spatial controller compares local exposure, colour, edge and clipping confidence to blend the candidates or retain a stronger candidate. This gives users a fast classical option, a pretrained deep option and an explainable hybrid; the evaluation shows that deep-only restoration currently gives the best average reference quality on LOL-v1.')

# Page 2
page();h('2 Technical Architecture and Implementation')
p('The React and TypeScript client sends images to a FastAPI service. The backend decodes and validates the image, converts it to float RGB, runs the requested method and stores outputs, intermediate maps and measured reports. References enter the evaluation stage only; they do not guide restoration. [R1]')
h('2 1 Classical Algorithmic Baseline',2)
p('The classical branch starts with a maximum-RGB illumination estimate. A luminance-guided filter smooths the estimate while retaining boundaries. The branch then applies bounded Retinex gain, bilateral denoising, luminance-only CLAHE, restrained white balance and saturation correction, followed by highlight preservation and artifact safeguards.')
p('Exposure severity is computed as s = clip((0.43 - mean luminance) / 0.43, 0, 1). At strength k, gamma is clip(1 - 0.64sk, 0.28, 1) and maximum gain is 1 + 4.5sk. The refined illumination has a floor of 0.025 + min(2n, 0.06), where n is a flat-region Haar noise estimate. Raising this floor for noisier inputs limits unstable amplification.')
p('Bilateral mixing increases with noise and darkness, while CLAHE mixing decreases as noise rises. The CLAHE grid adapts to image dimensions, and a support mask prevents the contrast stage from inventing illumination in completely black regions. Original highlights receive progressively stronger protection above luminance 0.65. These rules are implemented in backend/src/classical/pipeline.py; they are deterministic and do not use reference images.')
h('2 2 Deep Learning Pipeline',2)
p('The neural branch uses the official Retinexformer architecture and pretrained LOL-v1 checkpoint. Retinexformer combines illumination estimation with illumination-guided transformer restoration, making it a relevant starting point for spatially uneven low-light scenes. We reuse the published architecture rather than claim a new network design. [R2]')
p('The local configuration uses 40 feature channels, one stage and block counts [1, 2, 2]. The engine loads weights strictly, caches one model and runs in inference mode. Inputs are padded to compatible dimensions; larger images use overlapping tiles. The benchmark tile limit was 1024 pixels, so every 600 by 400 test image was processed as a whole frame.')
p('Deep mode runs independently of the classical pipeline and fusion controller. Missing weights are reported explicitly; automatic mode can fall back to classical processing. CUDA is selected only when available, with recovery to CPU for supported initialization or memory failures. See backend/src/deep/inference.py.')

# Page 3
page();h('2 3 Hybrid Integration and Adaptive Mechanism',2)
p('Classical maps and image statistics guide the external controller; they are not injected into Retinexformer or used to retrain its attention layers. Both candidates receive local confidence scores based on exposure suitability, agreement with input edges, flat-region residuals, chromaticity changes, newly clipped pixels and texture loss. These scores are uncalibrated heuristics, not probabilities of correctness.')
p('The neural mixing weight is a sigmoid of the confidence difference plus darkness and noise priors. A guided filter smooths this weight against the original luminance. Before safeguards, the fused image is w times the deep candidate plus (1 - w) times the classical candidate. The full hybrid protects bright input regions, redirects new clipping toward a safer candidate and applies bounded artifact corrections.')
p('The controller can reject fusion. For mildly underexposed inputs it may prefer a similarly confident classical candidate; otherwise, a candidate exceeding fused confidence by more than 0.025 can replace the fusion. The frontend exposes the selected method, explanation and contribution maps. Artifact maps identify heuristic risk and should not be interpreted as ground-truth defect labels. See backend/src/hybrid/controller.py.')
h('Training and dataset use',2)
p('LOL-v1 contains 485 paired training images and 15 paired test images. Our preparation script splits the official training partition reproducibly into 437 training and 48 development pairs with seed 42. The 15 official test pairs stay separate and are used for the reported comparisons. The pretrained model may already have seen the 48 development images during upstream training, so this development split does not establish unseen pretraining generalization. [R3, R4]')
p('We also ran one exploratory fine-tuning epoch using paired 64-pixel patches, batch size 2 and Adam at learning rate 0.0003. The implemented loss is mean Charbonnier error with epsilon squared 0.000001, plus 0.05 times the sum of horizontal and vertical gradient L1 errors. This is our optional adaptation objective, not a reproduction of the original training recipe. The script includes gradient clipping, a cosine scheduler, validation and checkpoint saving. [R5]')
p('The recorded training loss was 0.09063 and development loss was 0.10235. The adapted checkpoint reduced official-test PSNR from 25.1553 to 21.5054 dB and SSIM from 0.8441 to 0.8132. It was therefore not promoted: the application retains the original pretrained checkpoint. This outcome also cautions against choosing a model from NIQE alone, which improved slightly despite worse reference metrics.')
h('Frontend and processing outputs',2)
p('Six views cover restoration, image analysis, pipeline stages, independent model comparison, performance analytics and regional quality diagnostics. Analytics supports single-image ablations, batch jobs, completed benchmark reports and exports. The optional vivid finish and interpolated 4K export are presentation features; the reported benchmark and ablation runs do not apply them.')

# Page 4
page();h('3 Experimental Benchmarks and Evaluation')
h('3 1 Quantitative Benchmarks',2)
p('We report means over the official 15-image LOL-v1 test set, with 15 valid measurements for each metric and method. Evaluation uses aligned full RGB images in [0, 1], without border cropping, reference exposure adjustment or test-time optimization. All images remain at 600 by 400 pixels. The saved run was generated on 6 November 2026. [R6]')
table(['Approach','PSNR\ndB higher','SSIM\nhigher','LPIPS\nlower','NIQE\nlower','Latency\nms'],[
 (label,f"{mean(m,'psnr'):.4f}",f"{mean(m,'ssim'):.4f}",f"{mean(m,'lpips'):.4f}",f"{mean(m,'niqe'):.4f}",f"{mean(m,'latency_ms'):.1f}")
 for m,label in [('classical','Classical baseline'),('deep','Deep only'),('hybrid','Adaptive hybrid')]], [1.77,1.02,1.02,1.02,1.02,1.02])
caption('Table 1  Official test set averages from outputs/LOL-v1-final-benchmark/report.json')
p('Deep-only restoration leads all four quality metrics in this experiment, reaching 25.1553 dB PSNR. The hybrid improves substantially over the classical baseline but trails deep-only by 5.9965 dB PSNR and 0.0594 SSIM. Classical processing is the fastest option at 108.2 ms; running both candidates and the controller raises hybrid latency to 2565.8 ms.')
h('Metric interpretation and timing scope',2)
p('PSNR and SSIM compare the restored image with the aligned normal-light reference; higher values indicate closer agreement. LPIPS is also reference-based and lower is better. NIQE measures departures from a natural-image statistical model without a reference; a lower score alone does not prove better restoration. Genuine LPIPS and NIQE models were enabled for these runs, with no substituted scores.')
p('Latency is the restoration time recorded by each pipeline. Hybrid timing sums classical, neural and controller processing. It excludes upload, image decoding, report generation, perceptual-metric evaluation and browser rendering, and is not an end-to-end request benchmark. A first neural call can include initialization overhead. These are single-run CPU means, not repeated timing estimates with confidence intervals.')
h('Measured trade-off',2)
p('Average output clipping, defined as the fraction of pixels with any channel at least 254/255, was 0.4594% for deep-only and 0.0069% for hybrid. This shows a clipping trade-off, but it does not cancel the hybrid\'s lower reference fidelity or establish that all preserved highlights are perceptually correct. The confidence rules can favour conservative outputs that remain too dark relative to the reference.')
h('Runtime and reproducibility',2)
p('The recorded environment is Windows with Python 3.11.15, Node.js 22.14.0, PyTorch 2.7.0+cpu and torchvision 0.22.0+cpu. The benchmark sets CPU inference, a 2048-pixel processing limit and 1024-pixel tiles with 32-pixel overlap. The checkpoint SHA256 is recorded in both source reports. Actual NVIDIA CUDA performance was not measured on this machine. [R6, R8]')

# Page 5
page();h('3 2 Visual Outputs and Intermediate Representations',2)
p('The panels below use official test images and saved benchmark outputs. Panel order is identical in both figures. Display resizing preserves aspect ratio; no exposure normalization or vivid finish is applied. The normal-light reference is shown for comparison and was not available to the restoration algorithms.')
image(extreme)
caption('Figure 1  Extreme low light  LOL-v1 test image 493  Input versus deep output hybrid output and reference')
p('Image 493 has mean input luminance 0.0249 and is classified as extremely dark. The saved deep output reaches 22.5786 dB PSNR and 0.6992 SSIM; hybrid reaches 23.1574 dB and 0.6932 SSIM. The hybrid has slightly better PSNR for this image, although its SSIM is slightly lower. This example should not be generalized to the test-set average.')
image(backlit)
caption('Figure 2  Nonuniform illumination  LOL-v1 test image 780  Bright windows beside a dark interior')
p('Image 780 has a nonuniform-illumination score of 0.889. Deep-only output clipping is 0.2446%, compared with 0.0033% for hybrid, while deep-only has higher PSNR at 28.9842 versus 25.6671 dB. The scene illustrates the practical tension between lifting the interior and limiting bright-region saturation; the clipping statistic measures all pixels rather than a manually annotated highlight region.')
p('Repository figure sources: outputs/LOL-v1-final-benchmark/00006 and 00013. Their original.png, deep.png and hybrid.png files correspond to manifest test keys 493 and 780; references are under data/LOL-v1/eval15/high. Per-image values come from the same saved report. [R6]')

# Page 6
page();h('Intermediate Representations')
image(maps,width=6.3)
caption('Figure 3  Classical pipeline representations for official test image 493')
p('Maximum-RGB illumination and its guided refinement are grayscale intensities in [0, 1]. Reflectance is the clipped ratio of input RGB to refined illumination. The edge panel is the analyzer\'s Canny map, not a learned attention map. The final panel is the saved classical output; intermediate maps were regenerated from the same test input using the current classical implementation.')
p('These panels make parameter choices inspectable: illumination separates broad exposure structure, the reflectance estimate exposes noise and surface content, and edges help assess boundary preservation. They are algorithmic estimates, not physical ground truth. No claim is made that the neural model exported these particular maps. [R1, R6]')

# Page 7
page();h('3 3 Ablation Study',2)
p('The completed study applies nine variants to the same 15 official test images, producing 135 measured image-variant rows. Classical variants selectively disable denoising, CLAHE, colour correction and safeguards; fusion variants change fixed, global and spatial weighting. Values below are copied from the saved ablation report, with deltas calculated from unrounded means. [R7]')
labels={'retinex_only':'Retinex only','retinex_denoising':'Retinex plus denoising','retinex_clahe':'Retinex plus CLAHE','classical':'Complete classical','deep':'Deep only','fixed_fusion':'Fixed 50 50 fusion','global_fusion':'Global adaptive fusion','spatial_fusion':'Spatial without safeguards','full_hybrid':'Full hybrid'}
order=list(labels)
table(['Variant','PSNR\ndB','SSIM','LPIPS','NIQE','PSNR delta\nvs full'],[
 (labels[m],f"{ABL[m]['psnr']['mean']:.4f}",f"{ABL[m]['ssim']['mean']:.4f}",f"{ABL[m]['lpips']['mean']:.4f}",f"{ABL[m]['niqe']['mean']:.4f}",f"{ABL[m]['psnr']['mean']-ABL['full_hybrid']['psnr']['mean']:+.4f}") for m in order
],[2.12,.95,.9,.9,.9,1.1])
caption('Table 2  Nine variant ablation means  Higher PSNR and SSIM and lower LPIPS and NIQE are preferred')
h('Measured module effects',2)
p('Adding bilateral denoising to Retinex alone raises SSIM by 0.0047 and reduces LPIPS by 0.0045, while PSNR changes by only +0.0032 dB. Adding CLAHE to Retinex alone raises PSNR by 0.8364 dB but lowers SSIM by 0.0064 and increases LPIPS by 0.0257. More brightness and contrast therefore do not improve every quality measure.')
p('Spatial fusion without safeguards improves PSNR by 0.7380 dB and SSIM by 0.0435 over fixed 50/50 fusion, while reducing LPIPS by 0.0289. Global adaptive fusion, however, exceeds the full hybrid by 1.2671 dB PSNR and 0.0061 SSIM. Local weighting is therefore not uniformly better on this dataset.')
p('Full safeguards and candidate selection change PSNR by -0.0010 dB relative to spatial fusion without safeguards. Output clipping falls from 0.0109% to 0.0069%, but the aggregate reference metrics are almost unchanged. This comparison changes the safeguard and selection bundle together; it does not isolate the effect of each individual correction.')
p('Removing the classical candidate and controller entirely gives the deep-only result, which exceeds full hybrid by 5.9965 dB PSNR. That comparison removes a complete branch rather than a single learned guidance module. Future tests should separate colour correction, candidate switching and individual safeguards, repeat timings and evaluate additional unseen datasets.')

# Page 8
page();h('4 Failure Modes and Limitations')
h('Observed hybrid underexposure',2)
image(failure)
caption('Figure 4  Failure example  LOL-v1 test image 79  Conservative fusion loses reference fidelity')
ex=DATA['examples']['79']['rows']
p(f"For image 79, the deep-only candidate scores {ex['deep']['metrics']['psnr']['value']:.4f} dB PSNR and {ex['deep']['metrics']['ssim']['value']:.4f} SSIM, while hybrid falls to {ex['hybrid']['metrics']['psnr']['value']:.4f} dB and {ex['hybrid']['metrics']['ssim']['value']:.4f}. The PSNR gap is 13.3408 dB, the largest deep-versus-hybrid gap in the saved test comparison. The panels show that mixing in the conservative classical result can leave the output darker than the reference. [R6]")
h('Root cause and mitigation',2)
p('The controller rewards similarity to input edges and colour direction and penalizes clipping and high-frequency residuals. Those checks can mistake useful restoration changes for risk, especially when the input is a poor guide to the desired exposure. A candidate can therefore receive favourable heuristic confidence without matching the normal-light scene well.')
p('A practical current choice is deep mode when reference fidelity is the priority. Further work could calibrate candidate confidence on a separate development dataset, add an exposure-consistency criterion and learn fusion weights with reference supervision. Such changes must be tuned away from the official test set and evaluated on additional datasets before claiming improvement.')
h('Other limitations',2)
bullet('Clipped shadows contain no reliable scene detail. Gain and contrast can reveal existing signal but cannot recover information that was never recorded.')
bullet('The Haar residual estimate and artifact maps also respond to texture and exposure changes. They are diagnostic proxies, not calibrated sensor-noise or defect measurements.')
bullet('One-epoch adaptation worsened reference metrics and was rejected. The 15-image test set is small, and no cross-dataset robustness claim is supported.')
bullet('CUDA execution and browser visual responsiveness remain unverified in the saved evidence. The AMD Radeon 780M in this machine is not a CUDA-capable device.')
bullet('The optional 4K export is interpolation to a 3840-pixel long edge, not learned super-resolution. It does not reconstruct absent detail.')

# Page 9
page();h('5 Deployment and Quickstart Guide')
h('Quickstart commands',2)
p('Use PowerShell from a fresh checkout. Install Python 3.11, Node.js 22 and uv first. Model downloads require network access during setup; normal inference then uses local weights.')
code('''# Clone the project
git clone https://github.com/Tanish3115/Robust-Low-Light-Image-Restoration-and-Enhancement.git
cd Robust-Low-Light-Image-Restoration-and-Enhancement

# Create the Python environment and install the backend
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe -r backend/requirements.txt
Copy-Item .env.example .env

# Add neural restoration and perceptual quality metrics
uv pip install --python .venv/Scripts/python.exe `
  -r backend/requirements-deep.txt -r backend/requirements-iqa.txt
.venv/Scripts/python.exe scripts/setup_model.py --download
.venv/Scripts/python.exe scripts/setup_iqa.py --enable

# Build the frontend
cd frontend
npm ci
npm run build
cd ..

# Serve the built application and API
.venv/Scripts/python.exe -m uvicorn backend.app.main:app `
  --host 127.0.0.1 --port 8000''')
p('Open http://127.0.0.1:8000, upload a low-light image, select a mode and choose Enhance image. API documentation is at http://127.0.0.1:8000/docs. Classical mode works without the optional neural and IQA setup steps.')
h('Deployment format',2)
p('LumaRestore is a React/Vite frontend with a FastAPI backend and locally executed OpenCV and PyTorch pipelines. The backend serves the production frontend after a build. For development, run npm run dev in a second terminal under frontend and open http://127.0.0.1:5173. No paid AI inference API is required.')
p('A full CPU Docker image and a separate classical build target are provided. Provision the checkpoint and metric assets before starting Compose; it mounts local weights read-only. Stop any native backend already using port 8000, then run:')
code('docker compose up --build')
h('Reproduce the evaluation',2)
code('''.venv/Scripts/python.exe scripts/setup_dataset.py --download
.venv/Scripts/python.exe scripts/benchmark.py `
  --manifest data/LOL-v1/manifest.json --output outputs/report-benchmark `
  --config configs/benchmark.json
.venv/Scripts/python.exe scripts/benchmark.py `
  --manifest data/LOL-v1/manifest.json --output outputs/report-ablations `
  --config configs/benchmark.json --ablations''')
p('Use new output directories for each run. In the frontend, Performance analytics exposes Run all ablations, optional aligned references, batch experiments and report exports.')

# Page 10
page();h('Evidence and References')
p('The numerical tables use saved measured reports rather than values copied from a paper. Upstream resources are credited for the architecture and dataset; implementation-specific claims refer to repository modules.')
refs=[
 ('R1','Implementation modules','backend/src/analysis/analyzer.py; backend/src/classical/pipeline.py; backend/src/deep/inference.py; backend/src/hybrid/controller.py; backend/src/evaluation/experiments.py and metrics.py.'),
 ('R2','Retinexformer architecture and pretrained model','Cai et al. Retinexformer One-stage Retinex-based Transformer for Low-light Image Enhancement. ICCV 2023. Official source: https://github.com/caiyuanhao1998/Retinexformer and https://arxiv.org/abs/2303.06705.'),
 ('R3','LOL dataset origin','Wei et al. Deep Retinex Decomposition for Low-Light Enhancement. BMVC 2018. Dataset project: https://daooshee.github.io/BMVC2018website/.'),
 ('R4','Prepared dataset and split','data/LOL-v1/manifest.json and scripts/setup_dataset.py. Official training pairs 485; local split 437 training and 48 development; official test pairs 15.'),
 ('R5','Exploratory training and adaptation','scripts/finetune.py; outputs/LOL-v1-finetuning-validation/config.json and training.csv; outputs/LOL-v1-adaptation-test-comparison; BENCHMARK_RESULTS.md.'),
 ('R6','Main benchmark evidence','outputs/LOL-v1-final-benchmark/report.json and per-image output folders. 45 measured rows across three methods. Source run date 6 November 2026.'),
 ('R7','Ablation evidence','outputs/LOL-v1-final-ablations/report.json and backend/src/evaluation/experiments.py. 135 measured rows across nine variants.'),
 ('R8','Recorded implementation verification','VERIFICATION.md; outputs/device-validation.json; outputs/research-http-verification/verification.json; outputs/docker-research-verification/verification.json.'),
]
for tag,title,body in refs:
    para=p();r=para.add_run(f'[{tag}] {title}. ');r.bold=True;para.add_run(body)
h('Recorded verification',2)
p('The verification record dated 6 November 2026 reports 68 backend tests passed and 17 frontend tests passed, a successful TypeScript/Vite build, native and Docker HTTP checks, genuine neural inference and perceptual metrics, and completed official-test comparisons and ablations. These are recorded checks, not a new full test execution for this report. [R8]')
h('Student Submission Checklist',2)
p('[x] Repository URL and reproducible quickstart commands included.\n[x] Implementation explained without pasting raw source files.\n[x] Metric tables traced to measured reports with sample counts and protocol.\n[x] Test images and intermediate representations included.\n[ ] Enter the official problem ID and exact challenge title.\n[ ] Enter registered team name and all member details.\n[ ] Add the public demo or video link and confirm repository access.\n[ ] Confirm the final submission commit after local frontend text edits.')
p('The evaluated checkpoint fingerprint is 9b4810dc51322fab70be8658ee0ad1df64a54aa814497b7849767baa2ff32cd1. The current base commit is listed on the first page; the saved reports do not record an evaluated Git commit. Large datasets, checkpoints and outputs are ignored by Git, so include the required figures and reports in the submission package or regenerate them using the commands above.')

OUT.mkdir(parents=True,exist_ok=True)
dest=OUT/'LumaRestore_Technical_Solution_Report.docx'
doc.save(dest)
print(dest)
