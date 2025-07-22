from jet_bridge_base.utils.track_database import track_database_async
from jet_bridge_base.utils.track_model import track_model_async
from sqlalchemy.exc import SQLAlchemyError

from jet_bridge_base import status
from jet_bridge_base.configuration import configuration
from jet_bridge_base.responses.json import JSONResponse
from jet_bridge_base.utils.exceptions import validation_error_from_database_error


class DestroyAPIViewMixin(object):

    def destroy(self, request, *args, **kwargs):
        # Cache commonly used values from kwargs
        model_kwarg = kwargs.get('model')
        pk_kwarg = kwargs.get('pk')

        track_database_async(request)
        self.apply_timezone(request)
        request.apply_rls_if_enabled()

        instance = self.get_object(request)

        # Perform destroy in-place, save Model for error reporting
        model_cls = self.get_model(request)
        session = request.session

        # ---- perform_destroy split inline for perf: ----
        # all hot-path variables hoisted
        path_kwargs_model = request.path_kwargs['model']
        configuration.on_model_pre_delete(path_kwargs_model, instance)
        session.delete(instance)
        try:
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            # Fast error reporting; Model class passed
            raise validation_error_from_database_error(e, model_cls)
        configuration.on_model_post_delete(path_kwargs_model, instance)
        # -----------------------------------------------

        # Immediately build serializer and representation
        serializer = self.get_serializer(request, instance=instance)
        representation_data = serializer.representation_data

        # Use cached values for tracking
        track_model_async(request, model_kwarg, 'delete', pk_kwarg, representation_data)

        # Fast return; don't keep representation_data alive longer than needed
        return JSONResponse(status=status.HTTP_204_NO_CONTENT)

    def perform_destroy(self, request, instance):
        configuration.on_model_pre_delete(request.path_kwargs['model'], instance)
        Model = self.get_model(request)
        request.session.delete(instance)

        try:
            request.session.commit()
        except SQLAlchemyError as e:
            request.session.rollback()
            raise validation_error_from_database_error(e, Model)

        configuration.on_model_post_delete(request.path_kwargs['model'], instance)
