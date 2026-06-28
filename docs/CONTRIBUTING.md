# Panduan Kontribusi — Diamond

> **Terakhir Diperbarui:** June 23, 2026

Terima kasih telah mempertimbangkan untuk berkontribusi pada proyek Diamond! Dokumen ini menguraikan panduan untuk berkontribusi pada basis kode.

---

## Daftar Isi

- [Kode Etik](#kode-etik)
- [Memulai](#memulai)
- [Workflow Pengembangan](#workflow-pengembangan)
- [Standar Penulisan Kode](#standar-penulisan-kode)
- [Panduan Pengujian](#panduan-pengujian)
- [Proses Pull Request](#proses-pull-request)
- [Panduan Commit Git](#panduan-commit-git)
- [Dokumentasi](#dokumentasi)

---

## Kode Etik

Dengan berpartisipasi dalam proyek ini, Anda setuju untuk:

- Bersikap hormat dan inklusif
- Fokus pada masukan yang konstruktif
- Mengutamakan tujuan proyek
- Berkolaborasi secara terbuka

---

## Memulai

### Prasyarat

- Python 3.10+
- Git
- Pemahaman dasar tentang Django 5.2

### Persiapan Lingkungan Pengembangan

```bash
# 1. Fork and clone the repository
git clone https://github.com/<your-username>/diamond-web.git
cd diamond-web

# 2. Create virtual environment
python -m venv .venv

# 3. Activate it
# Windows (PowerShell):
Set-ExecutionPolicy Unrestricted -Scope Process; .\.venv\Scripts\Activate.ps1
# Linux/Mac:
# source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements/dev.txt

# 5. Setup environment
copy .env.example.dev .env  # Windows
# cp .env.example.dev .env  # Linux/Mac

# 6. Run migrations
python manage.py migrate

# 7. Load default templates (optional)
python manage.py load_default_templates

# 8. Create superuser
python manage.py createsuperuser

# 9. Run the server
python manage.py runserver
```

---

## Workflow Pengembangan

### Konvensi Penamaan Branch

Use the format: `{team-name}-{feature-description}`

```
esha-backend-fitur-login-logout
bimo-fitur-laporan-transfer
p3de-team-fix-tiket-workflow
```

### Proses Pengembangan

1. **Buat branch** dari `main`
2. **Lakukan perubahan** sesuai standar penulisan kode
3. **Tulis/perbarui pengujian** untuk perubahan Anda
4. **Jalankan pengujian** untuk memastikan tidak ada yang rusak
5. **Commit** dengan pesan commit yang bermakna
6. **Push** ke fork Anda
7. **Buat Pull Request**

### Sinkronisasi dengan Branch Main

```bash
git checkout main
git pull upstream main
git checkout your-feature-branch
git merge main
```

---

## Standar Penulisan Kode

### Python / Django

- Ikuti panduan gaya **PEP 8**
- Gunakan **4 spasi** untuk indentasi (tanpa tab)
- Panjang baris maksimal: **100 karakter** (PEP 8 merekomendasikan 79, tetapi 100 dapat diterima untuk Django)
- Gunakan **nama variabel yang bermakna** (Indonesia/Inggris konsisten dengan proyek)

### Ketentuan Khusus Django

- **Views**: Gunakan class-based views jika sesuai (ListView, CreateView, UpdateView, DeleteView)
- **Models**: Setiap model dalam file sendiri di `diamond_web/models/`
- **URLs**: Pertahankan struktur pola URL yang ada
- **Forms**: Tempatkan form di `diamond_web/forms/` dengan penamaan yang jelas
- **Templates**: Gunakan `diamond_web/templates/` dengan kelas Bootstrap 5
- **Queries**: Gunakan Django ORM, hindari SQL mentah kecuali sangat diperlukan
- **Context processors**: Untuk variabel template global

### Konvensi Penamaan

| Element | Convention | Example |
|---------|-----------|---------|
| Models | PascalCase | `Tiket`, `JenisDataILAP` |
| Views | PascalCase (CBV) | `TiketListView`, `ILAPCreateView` |
| Forms | PascalCase | `TiketForm`, `BackupDataForm` |
| URL patterns | snake_case | `tiket_list`, `ilap_data` |
| Templates | snake_case | `tiket_list.html`, `ilap_form.html` |
| Variables | snake_case | `nama_ilap`, `jumlah_baris` |
| Functions | snake_case | `get_next_ilap_id()` |

### Organisasi Impor

```python
# 1. Standard library
import os
import sys

# 2. Third-party
from django.shortcuts import render
from django.views.generic import ListView

# 3. Local
from ..models import Tiket
from ..forms import TiketForm
```

---

## Panduan Pengujian

### Menjalankan Pengujian

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest diamond_web/tests/test_tiket_workflow.py

# Run with coverage
pytest --cov-report=html

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration
```

### Menulis Pengujian

- **Unit tests**: Uji fungsi individu, form, dan metode model
- **Integration tests**: Uji view, workflow, dan interaksi database
- **Target cakupan**: Minimal **80%** untuk kode baru
- File pengujian ditempatkan di `diamond_web/tests/`
- Kelas pengujian: pola `Test*`
- Fungsi pengujian: pola `test_*`

### Apa yang Harus Diuji

- ✅ Validasi form (input valid dan tidak valid)
- ✅ Respons view (kode status, template yang digunakan, data konteks)
- ✅ Metode dan properti model
- ✅ Transisi workflow (perubahan status tiket)
- ✅ Pemeriksaan izin (akses berbasis peran)
- ✅ Pembuatan dan ekspor laporan
- ⚠️ Sinkronisasi Oracle (mock dependensi eksternal)

---

## Proses Pull Request

### Sebelum Mengirimkan

1. Pastikan kode Anda tidak mengandung error
2. Jalankan seluruh rangkaian pengujian: `pytest`
3. Perbarui dokumentasi jika diperlukan
4. Tinjau diff Anda sendiri terlebih dahulu

### Format Judul PR

```
type(scope): brief description
```

Examples:
```
feat(tiket): add bulk select for kirim tiket
fix(report): correct SLA calculation for weekends
docs(readme): update setup instructions
test(forms): add validation tests for tiket form
refactor(views): simplify home view logic
```

### Template Deskripsi PR

```markdown
## Description
Brief description of the changes.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update
- [ ] Refactoring

## Testing
- [ ] Unit tests pass
- [ ] Manual testing completed

## Screenshots (if applicable)

## Related Issues
Fixes #123
```

### Proses Review

1. Setidaknya **satu persetujuan** dari team lead diperlukan
2. Semua pemeriksaan otomatis harus lulus
3. Tanggapi semua komentar review sebelum merge
4. Squash commit sebelum merge (jika diminta)

---

## Panduan Commit Git

### Format Pesan Commit

```
type(scope): subject

body (optional)
```

### Tipe

| Type | Usage |
|------|-------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation changes |
| `test` | Adding/updating tests |
| `refactor` | Code refactoring |
| `style` | Formatting, missing semicolons, etc. |
| `chore` | Build tasks, dependencies, etc. |

### Contoh

```
feat(tiket): add ability to filter by date range in tiket list
fix(laporan): handle division by zero in SLA calculation
docs(oracle): update connection troubleshooting guide
test(forms): add validation for empty tiket form submission
```

---

## Dokumentasi

### Kapan Harus Memperbarui Dokumen

- Menambahkan fitur baru → perbarui dokumen terkait
- Mengubah workflow → perbarui dokumen alur status
- Menambahkan variabel lingkungan → perbarui `.env.example.*`
- Menambahkan model database → perbarui `docs/models_erd.md`
- Mengubah endpoint API → perbarui `docs/API_DOCUMENTATION.md`

### Lokasi Dokumen

| Document | Location | Description |
|----------|----------|-------------|
| Main README | `readme.md` | Project overview, setup, features |
| API Docs | `docs/API_DOCUMENTATION.md` | All API endpoints |
| Database Schema | `docs/models_erd.md` | ERD and model documentation |
| Deployment Guide | `docs/PRODUCTION_SETUP.md` | Production setup |
| Security Guide | `docs/SECURITY.md` | Security measures |
| Handover Doc | `docs/HANDOVER_DOCUMENT.md` | Project handover information |
| Oracle Setup | `docs/ORACLE_SETUP.md` | Oracle connection setup |
| Status Flow | `docs/status_tiket_flow.md` | Tiket workflow diagram |
| Templates Setup | `docs/TEMPLATES_SETUP.md` | DOCX template setup |
| Deployment Checklist | `docs/DEPLOYMENT_CHECKLIST.md` | Pre-deployment checklist |
| Changelog | `docs/CHANGELOG.md` | Release history |
| Contributing | `docs/CONTRIBUTING.md` | This file |

---

## Ada Pertanyaan?

Jika Anda memiliki pertanyaan tentang kontribusi, silakan buka diskusi di repositori atau hubungi pimpinan proyek.
