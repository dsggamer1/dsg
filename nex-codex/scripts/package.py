"""Create the complete source distribution without runtime data or credentials."""
from pathlib import Path
import argparse
import hashlib
import zipfile

parser = argparse.ArgumentParser()
parser.add_argument('output', type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
excluded_dirs = {'.venv', '__pycache__', '.pytest_cache', '.git', 'node_modules'}
files = []
for path in sorted(root.rglob('*')):
    relative = path.relative_to(root)
    if not path.is_file() or path.is_symlink() or any(part in excluded_dirs for part in relative.parts):
        continue
    if path.name == '.env' or path.name.endswith(('.db', '.db-wal', '.db-shm', '.pyc', '.zip')):
        continue
    if relative.parts[0] == 'private' and path.name != '.gitkeep':
        continue
    files.append(path)
# Always synthesize the distributed starter from the example, never the local .env.
from dotenv import dotenv_values
example = root / '.env.example'
values = dotenv_values(example)
secret_fields = ('DISCORD_TOKEN', 'DISCORD_CLIENT_SECRET', 'SESSION_SECRET', 'AI_API_KEY')
if any(values.get(key) for key in secret_fields):
    raise SystemExit('Refusing to package an example containing credentials.')
args.output.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(args.output, 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in files:
        archive.write(path, Path('NEX_CODEX')/path.relative_to(root))
    archive.writestr('NEX_CODEX/.env', example.read_text())
with zipfile.ZipFile(args.output) as archive:
    assert archive.testzip() is None
    required = {'README.md','PROJECT_STATE.md','CHANGELOG.md','requirements.txt','requirements.lock','.env.example','.env','main.py','nex/bot.py','nex/dashboard/app.py','nex/models.py'}
    names = set(archive.namelist())
    assert all('NEX_CODEX/'+name in names for name in required)
print(f'Packaged {len(files)+1} files into {args.output.name}')
print('SHA256 '+hashlib.sha256(args.output.read_bytes()).hexdigest())
