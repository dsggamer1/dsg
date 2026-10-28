"""Distribution safety checks run the actual packager on a synthetic project."""
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
import pytest


def starter(tmp_path):
    source=Path(__file__).resolve().parents[1]
    root=tmp_path/'source'
    shutil.copytree(source,root,ignore=shutil.ignore_patterns('.venv','__pycache__','.pytest_cache','*.db','*.db-*'))
    return root


def test_archive_excludes_local_credentials_and_runtime_data(tmp_path):
    root=starter(tmp_path)
    (root/'.env').write_text('DISCORD_TOKEN=synthetic-local-only\n')
    (root/'.env.local').write_text('PRIVATE_SENTINEL')
    (root/'nex'/'error.log').write_text('PRIVATE_SENTINEL')
    (root/'nex'/'secret.env').write_text('PRIVATE_SENTINEL')
    (root/'private'/'products'/'paid.zip').write_bytes(b'PRIVATE_SENTINEL')
    archive=tmp_path/'release.zip'
    result=subprocess.run([sys.executable,str(root/'scripts'/'package.py'),str(archive)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert z.read('NEX_CODEX/.env')==(root/'.env.example').read_bytes()
        assert 'NEX_CODEX/main.py' in z.namelist()
        assert len([n for n in z.namelist() if n.startswith('NEX_CODEX/nex/assets/emojis/') and n.endswith('.png')])==49
        assert z.read('NEX_CODEX/nex/assets/emojis/nex_cart.png').startswith(b'\x89PNG\r\n\x1a\n')
        assert len([n for n in z.namelist() if n.startswith('NEX_CODEX/nex/assets/help/') and n.endswith('.gif')])==4
        assert z.read('NEX_CODEX/nex/assets/help/home.gif').startswith(b'GIF89a')
        assert not any(b'PRIVATE_SENTINEL' in z.read(name) or b'synthetic-local-only' in z.read(name) for name in z.namelist() if not name.startswith('NEX_CODEX/tests/'))
        assert all(not name.startswith('/') and '..' not in Path(name).parts for name in z.namelist())


@pytest.mark.parametrize('entry',['SESSION_SECRET=synthetic-secret','OTHER_API_KEY=synthetic-secret','DATABASE_URL=postgresql://user:synthetic-secret@example.com/db'])
def test_packager_rejects_populated_example(tmp_path,entry):
    root=starter(tmp_path)
    (root/'.env.example').write_text(entry+'\n')
    archive=tmp_path/'release.zip'
    result=subprocess.run([sys.executable,str(root/'scripts'/'package.py'),str(archive)],capture_output=True,text=True)
    assert result.returncode!=0
    assert 'containing credentials' in result.stderr
    assert not archive.exists()
