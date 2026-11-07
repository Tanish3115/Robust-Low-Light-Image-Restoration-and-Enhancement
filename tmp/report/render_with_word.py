"""Use the packaged page renderer with Word conversion on Windows without bundled LibreOffice."""
from pathlib import Path
import importlib.util
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = Path('C:/Users/tanis/.cache/codex-runtimes/codex-primary-runtime')
RENDER = Path('C:/Users/tanis/.codex/plugins/cache/openai-primary-runtime/documents/26.1105.12137/skills/documents/render_docx.py')
os.environ['PATH'] = str(RUNTIME/'dependencies/native/poppler/Library/bin') + os.pathsep + os.environ['PATH']
spec=importlib.util.spec_from_file_location('render_docx',RENDER)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def convert_with_word(input_path,user_profile_dir,convert_tmp_dir,stem,verbose=False):
    output = Path(convert_tmp_dir)/(Path(input_path).stem+'.pdf')
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass',
        '-File',str(ROOT/'tmp/report/export_word.ps1'),'-InputDocx',str(Path(input_path).resolve()),
        '-OutputPdf',str(output.resolve())],capture_output=True,text=True,timeout=100)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    return str(output),result.stdout

module.convert_to_pdf=convert_with_word
sys.argv=['render_docx.py',str(ROOT/'report/LumaRestore_Technical_Solution_Report.docx'),
    '--output_dir',str(ROOT/'tmp/report/render_architecture'),'--emit_pdf','--dpi','125']
module.main()
