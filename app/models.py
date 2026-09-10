from django.db import models
from django.utils.text import slugify
from django.core.exceptions import ValidationError
import math
import logging
from tinymce.models import HTMLField
from django.core.validators import FileExtensionValidator
from io import BytesIO
from PIL import Image
from django.core.files.base import ContentFile

# Allow Pillow to process large, high-resolution project screenshots without DecompressionBomb limits
Image.MAX_IMAGE_PIXELS = None

logger = logging.getLogger(__name__)

def optimize_image_field(image_field, high_quality=True):
    """Automatically compress and convert any uploaded image to optimized WebP format"""
    if not image_field or not image_field.name:
        return
        
    ext = image_field.name.split('.')[-1].lower()
    if ext in ['svg', 'pdf', 'ico']:
        return

    try:
        image_field.file.seek(0)
        img = Image.open(image_field.file)
        
        # Determine maximum bounding box
        max_size = (1600, 1200) if high_quality else (300, 300)
        quality = 85 if high_quality else 80

        # Resize if larger than max_size
        if img.width > max_size[0] or img.height > max_size[1]:
            img.thumbnail(max_size, Image.Resampling.LANCZOS)

        # Convert RGBA to RGB for JPEG-origin files if needed, or preserve alpha for transparent webp
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            pass
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        output = BytesIO()
        img.save(output, format='WEBP', quality=quality, optimize=True)
        output.seek(0)

        # Set new .webp filename
        base_name = image_field.name.rsplit('.', 1)[0]
        new_name = f"{base_name}.webp"
        image_field.save(new_name, ContentFile(output.read()), save=False)
    except Exception as e:
        logger.warning(f"Image optimization skipped for {image_field.name}: {e}")

def validate_file_size(value):
    limit = 5 * 1024 * 1024  # 5MB
    if value.size > limit:
        raise ValidationError("File size must be under 5MB.")

class Resume(models.Model):
    file = models.FileField(
        upload_to="resumes/",
        validators=[
            FileExtensionValidator(allowed_extensions=["pdf", "doc", "docx"]),
            validate_file_size
        ]
    )
    uploaded_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ["-uploaded_at"]


# Project Model
class Project(models.Model):
    title = models.CharField(max_length=255, db_index=True)
    categories = models.CharField(max_length=255, help_text="Separate categories with commas", default="Uncategorized", db_index=True)
    publication_date = models.DateTimeField(auto_now_add=True, db_index=True)
    tags = models.CharField(max_length=255)
    description = models.TextField(max_length=500)
    skills = models.ManyToManyField("Skill", related_name="project_skills")
    slug = models.SlugField(unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    problem_statement = models.TextField(max_length=500, null=True, blank=True)
    solution = models.TextField(max_length=500, null=True, blank=True)
    impact = models.TextField(max_length=500, null=True, blank=True)

    # Fields for GitHub and Live Project link
    github_link = models.URLField(max_length=500, null=True, blank=True, help_text="GitHub repository link")
    live_link = models.URLField(max_length=500, null=True, blank=True, help_text="Live project link")

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Project.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_category_list(self):
        return [cat.strip() for cat in self.categories.split(",") if cat.strip()]

    def get_tag_list(self):
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(",") if tag.strip()]

    def __str__(self):
        return self.title


class ProjectImage(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="projects/images/")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        optimize_image_field(self.image, high_quality=True)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Image for {self.project.title}"


class Feature(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="features")
    image = models.ImageField(upload_to="projects/features/")
    title = models.CharField(max_length=255)
    description = models.TextField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        optimize_image_field(self.image, high_quality=True)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.title} - {self.project.title}"


class Learning(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="learnings")
    paragraph = models.TextField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Learning for {self.project.title}"


class Blog(models.Model):
    title = models.CharField(max_length=255, db_index=True)
    content = HTMLField()  # Using TinyMCE for rich-text content
    image = models.ImageField(upload_to="blogs/")
    publication_date = models.DateTimeField(auto_now_add=True, db_index=True)
    slug = models.SlugField(unique=True, blank=True)
    categories = models.CharField(max_length=255, help_text="Separate categories with commas", default="Uncategorized", db_index=True)
    time_to_read = models.PositiveIntegerField(default=1, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Blog.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug

        self.time_to_read = self.calculate_reading_time()
        optimize_image_field(self.image, high_quality=True)
        super().save(*args, **kwargs)

    def calculate_reading_time(self):
        words_per_minute = 200
        word_count = len(self.content.split())
        return max(1, math.ceil(word_count / words_per_minute))

    def get_category_list(self):
        return [cat.strip() for cat in self.categories.split(",") if cat.strip()]

    def __str__(self):
        return self.title


class ExperienceQuerySet(models.QuerySet):
    def prioritized(self):
        return self.annotate(
            is_current=models.Case(
                models.When(end_date__isnull=True, then=models.Value(1)),
                default=models.Value(0),
                output_field=models.IntegerField()
            )
        ).order_by("-is_current", "-start_date", "-created_at")


class ExperienceManager(models.Manager):
    def get_queryset(self):
        return ExperienceQuerySet(self.model, using=self._db).annotate(
            is_current=models.Case(
                models.When(end_date__isnull=True, then=models.Value(1)),
                default=models.Value(0),
                output_field=models.IntegerField()
            )
        ).order_by("-is_current", "-start_date", "-created_at")


# Experience Model
class Experience(models.Model):
    title = models.CharField(max_length=255, db_index=True)
    image = models.ImageField(upload_to="experience/")
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(null=True, blank=True)
    description = models.TextField()
    categories = models.CharField(max_length=255, help_text="Separate categories with commas", default="Uncategorized", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ExperienceManager()

    class Meta:
        ordering = ["-start_date"]

    def save(self, *args, **kwargs):
        optimize_image_field(self.image, high_quality=True)
        super().save(*args, **kwargs)

    def get_category_list(self):
        return [cat.strip() for cat in self.categories.split(",") if cat.strip()]

    def __str__(self):
        return self.title


# FAQ Model
class FAQ(models.Model):
    question = models.CharField(max_length=300, db_index=True)
    answer = models.TextField()
    categories = models.CharField(max_length=255, help_text="Separate categories with commas", default="Uncategorized", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def clean(self):
        super().clean()
        if not self.pk and FAQ.objects.count() >= 6:
            raise ValidationError("Maximum limit reached: You can only add up to 6 FAQs. Please edit or delete an existing FAQ.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_category_list(self):
        return [cat.strip() for cat in self.categories.split(",") if cat.strip()]

    def __str__(self):
        return self.question


# Skill Model
class Skill(models.Model):
    STATUS_CHOICES = [
        ("Expert", "Expert"),
        ("Learning", "Learning"),
        ("Average", "Average"),
    ]

    name = models.CharField(max_length=100, unique=True, db_index=True)
    icon = models.ImageField(upload_to="skills/icons/", blank=True, null=True, help_text="Leave blank to auto-fetch from free developer icon libraries (Devicon / SimpleIcons / SkillIcons), or upload your own.")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="Learning")
    level = models.PositiveIntegerField(default=50, db_index=True)
    description = models.TextField(max_length=500, blank=True)
    categories = models.CharField(max_length=255, help_text="Separate categories with commas", default="Uncategorized", db_index=True)
    certificate = models.FileField(upload_to="skills/certificates/", blank=True, null=True, help_text="Upload a certificate image, PDF, or DOC file")
    resource_links = models.TextField(blank=True, help_text="Enter resource links separated by commas (YouTube, PDFs, Docs, Images)")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-level", "name"]

    def save(self, *args, **kwargs):
        # If user didn't provide an icon, attempt auto-discovery from free icon libraries
        if not self.icon:
            try:
                from .icon_fetcher import auto_assign_skill_icon
                auto_assign_skill_icon(self)
            except Exception as e:
                logger.warning(f"Failed to auto-fetch icon for skill '{self.name}': {e}")

        optimize_image_field(self.icon, high_quality=False)
        super().save(*args, **kwargs)

    def get_icon_url(self):
        if self.icon and hasattr(self.icon, 'url'):
            return self.icon.url
        return "/static/images/icons/default.webp"

    def get_category_list(self):
        return [cat.strip() for cat in self.categories.split(",") if cat.strip()]

    def get_resource_list(self):
        return [res.strip() for res in self.resource_links.split(",") if res.strip()]

    def __str__(self):
        return f"{self.name} ({self.level}%)"


class ContactMessage(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField()
    subject = models.CharField(max_length=255)
    message = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True, help_text="Sender IP address")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return f"{self.name} - {self.subject}"
