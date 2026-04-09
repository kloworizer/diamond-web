"""Form for DOCX Template management."""

from django import forms
from ..models.docx_template import DocxTemplate


class DocxTemplateForm(forms.ModelForm):
    """Form for creating and updating DOCX templates."""
    
    class Meta:
        model = DocxTemplate
        fields = ['nama_template', 'deskripsi', 'jenis_dokumen', 'file_template', 'active']
        widgets = {
            'nama_template': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nama template dokumen'
            }),
            'deskripsi': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Deskripsi template dokumen'
            }),
            'jenis_dokumen': forms.Select(attrs={
                'class': 'form-select',
            }),
            'file_template': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.docx'
            }),
            'active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }
        labels = {
            'nama_template': 'Nama Template',
            'deskripsi': 'Deskripsi',
            'jenis_dokumen': 'Jenis Dokumen',
            'file_template': 'File Template (.docx)',
            'active': 'Aktif',
        }
