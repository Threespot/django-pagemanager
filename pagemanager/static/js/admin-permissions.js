(function($){
$(document).ready(function() {
    
    
    var disable_selector = function (selector) {
        var select = $(selector).addClass("disabled")
            .find("select")
            .attr("disabled", "true");
        // Disabled fieds don't get included in forms, so create a hidden field with the value in it: Django still needs the value.
        var shadow_field = $('<input type="hidden" name="' + select.attr("name") + '" value="' + select.attr("value") + '"/>');
        select.after(shadow_field);
    }
    
    // Disable staus and/or visibilty if user is not authorized to change them.
    if (!permission_settings['change_status']) {
        disable_selector(".form-row.status");
    }
    if (!permission_settings['change_visibility']) {
        // Remove "public" option from choices in add page if user is not authorized to change visibility .
        if (window.location.href.match(/\/add\//)) {
            $(".form-row.visibility select option:first").remove();
        }
        disable_selector(".form-row.visibility");
    }
    
    // Disable saving /deleting for published pages if user is not authorized to do so.
    if (!permission_settings['modify_published_pages'] && permission_settings['is_published']) {
        $(".submit-row").remove();
    }
    // Remove "publish" option from choices if user is not authorized to change published pages.
    if (!permission_settings['modify_published_pages'] && !permission_settings['is_published']) {
        $(".form-row.status select option:last").remove();
    }

});
})(django.jQuery);