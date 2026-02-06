"""
Base classes for tiket workflow steps.
"""

from django.views.generic import CreateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.db import transaction
import logging

from ..mixins import UserP3DERequiredMixin

logger = logging.getLogger(__name__)


class WorkflowStepMixin:
    """Base mixin for workflow step views."""
    
    def get_json_response(self, success=True, message="", errors=None, redirect=None):
        """Generate standardized JSON response for AJAX requests."""
        response = {
            'success': success,
            'message': message,
        }
        if errors:
            response['errors'] = errors
        if redirect:
            response['redirect'] = redirect
        return JsonResponse(response)
    
    def is_ajax_request(self):
        """Check if the request is an AJAX request."""
        return self.request.headers.get('X-Requested-With') == 'XMLHttpRequest'


class WorkflowStepCreateView(LoginRequiredMixin, UserP3DERequiredMixin, WorkflowStepMixin, CreateView):
    """Base create view for workflow steps."""
    
    def form_valid(self, form):
        """Handle form submission with transaction management."""
        logger.info(f"form_valid called for {self.__class__.__name__}")
        try:
            with transaction.atomic():
                response = self.perform_workflow_action(form)
                logger.info(f"perform_workflow_action returned: {type(response)}")
                
                if isinstance(response, JsonResponse):
                    logger.info("Returning JsonResponse")
                    return response
                
                # If perform_workflow_action returns None and object is already saved,
                # redirect to success URL instead of saving again
                if response is None and hasattr(self, 'object') and self.object and self.object.pk:
                    logger.info(f"Object already saved with pk={self.object.pk}, redirecting to success URL")
                    return self.successful_redirect()
                
                logger.info("Calling super().form_valid(form)")
                return super().form_valid(form)
        except Exception as e:
            logger.error(f"Exception in form_valid: {str(e)}", exc_info=True)
            return self.handle_form_error(form, str(e))
    
    def successful_redirect(self):
        """Redirect to success URL."""
        from django.shortcuts import redirect
        return redirect(self.get_success_url())
    
    def form_invalid(self, form):
        """Handle form validation errors."""
        logger.warning(f"form_invalid called: {form.errors}")
        if self.is_ajax_request():
            return self.get_json_response(
                success=False,
                errors=form.errors
            )
        return super().form_invalid(form)
    
    def perform_workflow_action(self, form):
        """Override in subclasses to implement workflow-specific logic."""
        return None
    
    def handle_form_error(self, form, error_message):
        """Handle errors during form processing."""
        if self.is_ajax_request():
            return self.get_json_response(
                success=False,
                errors={'__all__': [error_message]}
            )
        return self.form_invalid(form)


class WorkflowStepDetailView(LoginRequiredMixin, UserP3DERequiredMixin, DetailView):
    """Base detail view for workflow steps."""
    pass
