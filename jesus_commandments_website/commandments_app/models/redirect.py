from django.db import models
from url_or_relative_url_field.fields import URLOrRelativeURLField


class Redirect(models.Model):
    url = URLOrRelativeURLField()
