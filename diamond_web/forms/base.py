from django import forms


class AutoRequiredFormMixin:
    """
    Mixin that automatically sets required status on ModelForm fields
    based on the model field's nullability.

    Rules applied only to fields NOT explicitly declared as class-level
    attributes on the form (declared fields keep their own required setting):
      - model field has null=True AND blank=True  → required=False
      - model field has no null=True and is not BooleanField → required=True

    Crispy forms (bootstrap5) will then automatically render a red asterisk
    for every field where required=True, with no manual template changes needed.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not (hasattr(self, 'Meta') and hasattr(self.Meta, 'model')):
            return
        model = self.Meta.model
        # Fields declared as class-level attributes on the form manage their
        # own required status — skip them so we don't override intent.
        declared = getattr(self, 'declared_fields', {})
        for field_name, form_field in self.fields.items():
            if field_name in declared:
                continue
            try:
                model_field = model._meta.get_field(field_name)
                null = getattr(model_field, 'null', False)
                blank = getattr(model_field, 'blank', False)
                if null and blank:
                    form_field.required = False
                elif not null:
                    # Non-nullable fields are required, including BooleanFields
                    # (they always have a value via default or user selection)
                    form_field.required = True
            except Exception:
                # Field not on model (e.g. reverse relations, custom) — skip
                pass
