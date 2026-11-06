from pathlib import Path
import subprocess
import sys


def test_failed_model_setup_preserves_source_even_with_download_suffix(tmp_path):
    root=Path(__file__).resolve().parents[1]
    source=tmp_path/'LOL_v1.download';source.write_bytes(b'original source must survive failed validation')
    result=subprocess.run([sys.executable,str(root/'scripts/setup_model.py'),'--source',str(source),
                           '--output',str(tmp_path/'LOL_v1.pth'),'--sha256','0'*64],capture_output=True,text=True)
    assert result.returncode!=0
    assert 'SHA256 mismatch' in result.stderr
    assert source.read_bytes()==b'original source must survive failed validation'
    assert not list(tmp_path.glob('.lumarestore-*'))
