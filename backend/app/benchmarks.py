"""Read-only discovery of completed CLI benchmark results in the output root."""
import json
from pathlib import Path
import re
import tempfile
import zipfile

NAME=re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$')
SUFFIXES={'.json','.csv','.svg','.png'}


class BenchmarkCatalog:
    def __init__(self,root:Path):self.root=root.resolve()

    def folder(self,name):
        if not NAME.fullmatch(name):raise KeyError('Unknown benchmark')
        path=self.root/name
        if path.is_symlink() or path.resolve().parent!=self.root:raise KeyError('Unknown benchmark')
        return path

    def read(self,name):
        try:
            path=self.folder(name)/'report.json'
            if path.stat().st_size>30*1024**2:raise KeyError('Report exceeds the display limit')
            record=json.loads(path.read_text(encoding='utf-8'))
            if not record.get('averages') or not record.get('per_image'):raise KeyError('Not a completed measured report')
            keys=list(dict.fromkeys(row['key'] for row in record['per_image']))
            for row in record['per_image']:
                index=keys.index(row['key'])
                row['artifact']=f"/api/benchmarks/{name}/artifacts/{index:05d}/{row['mode']}.png"
                row['original']=f'/api/benchmarks/{name}/artifacts/{index:05d}/original.png'
            return record
        except (OSError,ValueError,TypeError) as exc:raise KeyError('Benchmark report is unavailable.') from exc

    def list(self):
        records=[]
        for path in self.root.iterdir():
            if not path.is_dir() or path.is_symlink() or not NAME.fullmatch(path.name):continue
            try:
                report=self.read(path.name)
                records.append({'id':path.name,'created_at':report.get('created_at'),'partition':report['partition'],
                                'ablations':report.get('ablations',False),'images':len({row['key'] for row in report['per_image']}),
                                'methods':len(report['averages'])})
            except (KeyError,TypeError):continue
        return sorted(records,key=lambda row:row.get('created_at') or '',reverse=True)

    def artifact(self,name,artifact):
        self.read(name)
        root=self.folder(name).resolve();path=(root/artifact).resolve()
        if not path.is_relative_to(root) or path.is_symlink() or not path.is_file() or path.suffix not in SUFFIXES:raise KeyError('Unknown benchmark artifact')
        return path

    def archive(self,name):
        self.read(name);root=self.folder(name).resolve()
        cache=self.root/'.downloads';cache.mkdir(exist_ok=True);path=cache/f'{name}.zip'
        if path.is_file() and path.stat().st_mtime>=(root/'report.json').stat().st_mtime:return path
        with tempfile.NamedTemporaryFile(dir=cache,suffix='.zip',delete=False) as stream:temporary=Path(stream.name)
        try:
            with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as archive:
                for file in root.rglob('*'):
                    if file.is_file() and not file.is_symlink() and file.resolve().is_relative_to(root) and file.suffix in SUFFIXES:archive.write(file,file.relative_to(root))
            temporary.replace(path)
        finally:temporary.unlink(missing_ok=True)
        return path
