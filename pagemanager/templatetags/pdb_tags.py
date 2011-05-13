from django import template

register = template.Library()


class PdbNode(template.Node):

    def render(self, context):
        import pdb; pdb.set_trace()
        return ''

@register.tag
def pdb(parser, token):
    """
    In any admin change_view, adds the object being changed to the context
    """
    return PdbNode()


class IpdbNode(template.Node):

    def render(self, context):
        import ipdb; ipdb.set_trace()
        return ''

@register.tag
def ipdb(parser, token):
    """
    In any admin change_view, adds the object being changed to the context
    """
    return IpdbNode()