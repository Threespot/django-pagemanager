from django.dispatch import Signal


page_moved = Signal(providing_args=["branch_ids"])

page_edited = Signal(providing_args=["page, created"])