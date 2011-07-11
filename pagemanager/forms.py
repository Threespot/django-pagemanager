from django import forms

from pagemanager.permissions import get_published_status_name

class PageAdminFormMixin(object):
    
    def clean(self):
        """
        Make sure that an item that is a draft copy is always unpublished.
        """
        cleaned_data = super(PageAdminFormMixin, self).clean()
        status = cleaned_data.get('status')
        copy_of = self.instance.copy_of
        if status == get_published_status_name() and copy_of:
            model_name = self.instance._meta.verbose_name
            raise forms.ValidationError((
                "This %s is an unpublished draft copy of a %s that is already "
                "published. If you want to publish this over top of the " 
                "existing item, you can do so by merging it."
            ) % (model_name, model_name))
        return cleaned_data