from django.contrib import admin
from . import models

# Register your models here.
admin.site.register(models.Category)
admin.site.register(models.Inventory)
admin.site.register(models.Product)
admin.site.register(models.Location)
admin.site.register(models.Supplier)
admin.site.register(models.AuditLog)
admin.site.register(models.StockAdjustmentRequest)