"""Safely prepare the authors' LOL-v1 archive and preserve its official split."""
import argparse
import hashlib
import json
from pathlib import Path,PurePosixPath
import shutil
import sys
import urllib.request
import zipfile
import zlib

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.src.evaluation.datasets import pair_images,split_manifest

SOURCE_PAGE='https://daooshee.github.io/BMVC2018website/'
SOURCE_FILE='157bjO1_cFuSd0HWDUuAmcHRJDVyWpOxB'


def prepare(archive:Path,output:Path,*,sha256:str|None=None,resume:bool=False):
    if not zipfile.is_zipfile(archive):raise ValueError('Archive is not a complete ZIP file. The download may still be running or Drive may have returned an HTML error.')
    if output.exists() and any(output.iterdir()) and not resume:raise ValueError('Use an empty output directory, or --resume to CRC-validate existing archive members without replacing them.')
    with archive.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    if sha256 and sha256.lower()!=digest:raise ValueError('Dataset checksum mismatch.')
    output.mkdir(parents=True,exist_ok=True);root=output.resolve()
    with zipfile.ZipFile(archive) as data:
        if sum(info.file_size for info in data.infolist())>2_000_000_000:raise ValueError('Archive exceeds the 2 GB extraction safety limit.')
        for info in data.infolist():
            name=PurePosixPath(info.filename.replace('\\','/'))
            if name.is_absolute() or '..' in name.parts or any(':' in part for part in name.parts):raise ValueError('Unsafe archive member path.')
            if (info.external_attr>>16)&0o170000==0o120000:raise ValueError('Symbolic links are not accepted in dataset archives.')
            if '__MACOSX' in name.parts or name.name.startswith('._'):continue
            if info.is_dir() or name.suffix.lower() not in {'.png','.jpg','.jpeg','.webp','.txt'}:continue
            path=(root/str(name)).resolve()
            if not path.is_relative_to(root):raise ValueError('Archive path escapes the output directory.')
            path.parent.mkdir(parents=True,exist_ok=True)
            if path.exists():
                crc=0
                with path.open('rb') as stream:
                    while chunk:=stream.read(1024**2):crc=zlib.crc32(chunk,crc)
                if path.stat().st_size!=info.file_size or crc!=info.CRC:raise ValueError('Existing dataset member differs from the archive; no files were overwritten.')
                continue
            with data.open(info) as source,path.open('wb') as target:shutil.copyfileobj(source,target)
    training=[path for path in root.rglob('our485/low') if '__MACOSX' not in path.parts]
    testing=[path for path in root.rglob('eval15/low') if '__MACOSX' not in path.parts]
    if len(training)!=1 or len(testing)!=1:raise ValueError('Expected one our485/low and one eval15/low official partition.')
    train=pair_images(training[0],training[0].parent/'high');test=pair_images(testing[0],testing[0].parent/'high')
    if len(train)!=485 or len(test)!=15:raise ValueError(f'Official LOL-v1 count mismatch: {len(train)} training and {len(test)} test pairs.')
    manifest=split_manifest(train,test,seed=42,validation_fraction=.1)
    manifest['dataset']={'name':'LOL-v1','source_page':SOURCE_PAGE,'source_file_id':SOURCE_FILE,'archive_sha256':digest,
                         'counts':{'official_training':485,'official_test':15},
                         'usage':'Research dataset from its authors. Dataset files are not redistributed in this repository.'}
    (root/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,default=ROOT/'data/downloads/LOLdataset.zip')
    parser.add_argument('--download',action='store_true');parser.add_argument('--output',type=Path,default=ROOT/'data/LOL-v1')
    parser.add_argument('--sha256')
    parser.add_argument('--resume',action='store_true',help='Validate already-extracted members against archive CRCs and finish preparing the manifest.')
    args=parser.parse_args()
    if args.download:
        if args.archive.exists():parser.error('Archive already exists; omit --download to validate and use it.')
        args.archive.parent.mkdir(parents=True,exist_ok=True)
        urllib.request.urlretrieve(f'https://drive.usercontent.google.com/download?id={SOURCE_FILE}&export=download&confirm=t',args.archive)
    manifest=prepare(args.archive,args.output,sha256=args.sha256,resume=args.resume)
    print(json.dumps({'dataset':manifest['dataset'],'partitions':{key:len(manifest[key]) for key in ('train','validation','test')}},indent=2))
