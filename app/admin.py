from django.contrib import admin
from django.db import models
from django.utils.html import format_html, mark_safe
from tinymce.widgets import TinyMCE
from .models import (
    Project, Skill, Experience, Blog, ProjectImage, Feature, Learning, FAQ, ContactMessage, Resume
)

@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = ("resume_preview", "file_name", "uploaded_at", "download_action")
    readonly_fields = ("uploaded_at",)

    def resume_preview(self, obj):
        return format_html('<span style="font-size:20px;">📄</span>')
    resume_preview.short_description = ""

    def file_name(self, obj):
        if obj.file:
            return obj.file.name.split('/')[-1]
        return "No file"
    file_name.short_description = "Resume File"

    def download_action(self, obj):
        if obj.file:
            return format_html(
                '<a href="{}" target="_blank" class="button" style="padding: 4px 10px; background: rgba(99,102,241,0.2); border: 1px solid #6366f1; color: #a5b4fc; border-radius: 4px; text-decoration: none;">Download</a>',
                obj.file.url
            )
        return "-"
    download_action.short_description = "Action"


class ProjectImageInline(admin.TabularInline):
    model = ProjectImage
    extra = 1
    fields = ("image", "image_preview")
    readonly_fields = ("image_preview",)

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 48px; max-width: 80px; object-fit: cover; border-radius: 4px; border: 1px solid #334155;" />', obj.image.url)
        return "-"
    image_preview.short_description = "Preview"


class FeatureInline(admin.StackedInline):
    model = Feature
    extra = 1
    fields = (("title", "image"), "description")


class LearningInline(admin.TabularInline):
    model = Learning
    extra = 1


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("cover_thumbnail", "title", "category_badges", "skills_summary", "publication_date", "links_column")
    list_filter = ("categories", "publication_date")
    search_fields = ("title", "description", "categories", "tags")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("skills",)
    inlines = [ProjectImageInline, FeatureInline, LearningInline]

    fieldsets = (
        ("Core Information", {
            "fields": ("title", "slug", "categories", "tags", "description", "skills")
        }),
        ("Case Study Deep Dive", {
            "fields": ("problem_statement", "solution", "impact"),
            "classes": ("collapse",)
        }),
        ("External Links", {
            "fields": ("github_link", "live_link")
        }),
    )

    def cover_thumbnail(self, obj):
        first_img = obj.images.first()
        if first_img and first_img.image:
            return format_html('<img src="{}" style="width: 44px; height: 32px; object-fit: cover; border-radius: 4px; border: 1px solid #334155;" />', first_img.image.url)
        return format_html('<span style="display:inline-block; width:44px; height:32px; background:#1e293b; border-radius:4px; text-align:center; line-height:32px; font-size:14px;">💼</span>')
    cover_thumbnail.short_description = "Cover"

    def category_badges(self, obj):
        cats = obj.get_category_list()
        badges = [f'<span style="display:inline-block; padding: 2px 7px; margin: 1px; background: rgba(99,102,241,0.18); border: 1px solid rgba(99,102,241,0.35); border-radius: 4px; font-size: 11px; color: #a5b4fc;">{c}</span>' for c in cats]
        return mark_safe(" ".join(badges)) if badges else "-"
    category_badges.short_description = "Categories"

    def skills_summary(self, obj):
        count = obj.skills.count()
        return format_html('<span style="color:#cbd5e1; font-weight:600;">⚡ {} Skills</span>', count)
    skills_summary.short_description = "Tech Stack"

    def links_column(self, obj):
        links = []
        if obj.github_link:
            links.append(f'<a href="{obj.github_link}" target="_blank" title="GitHub" style="color:#38bdf8; margin-right:6px;">🐙 GitHub</a>')
        if obj.live_link:
            links.append(f'<a href="{obj.live_link}" target="_blank" title="Live Preview" style="color:#34d399;">🔗 Live</a>')
        return mark_safe(" | ".join(links)) if links else "-"
    links_column.short_description = "Links"


@admin.register(Blog)
class BlogAdmin(admin.ModelAdmin):
    formfield_overrides = {
        models.TextField: {'widget': TinyMCE(attrs={'cols': 80, 'rows': 25})},
    }
    list_display = ("cover_preview", "title", "category_badges", "time_to_read_display", "publication_date")
    list_filter = ("categories", "publication_date")
    search_fields = ("title", "content", "categories")
    prepopulated_fields = {"slug": ("title",)}

    def cover_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 44px; height: 32px; object-fit: cover; border-radius: 4px; border: 1px solid #334155;" />', obj.image.url)
        return format_html('<span style="font-size:16px;">📝</span>')
    cover_preview.short_description = "Cover"

    def category_badges(self, obj):
        cats = obj.get_category_list()
        badges = [f'<span style="display:inline-block; padding: 2px 7px; margin: 1px; background: rgba(99,102,241,0.18); border: 1px solid rgba(99,102,241,0.35); border-radius: 4px; font-size: 11px; color: #a5b4fc;">{c}</span>' for c in cats]
        return mark_safe(" ".join(badges)) if badges else "-"
    category_badges.short_description = "Categories"

    def time_to_read_display(self, obj):
        return format_html('<span style="color:#cbd5e1;">⏱️ {} min</span>', obj.time_to_read)
    time_to_read_display.short_description = "Read Time"


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("icon_preview", "name", "level_bar", "status_badge", "category_badges")
    list_filter = ("status", "level", "categories")
    search_fields = ("name", "categories", "description")

    fieldsets = (
        ("Skill Details", {
            "fields": ("name", "status", "level", "categories", "description")
        }),
        ("Icon & Auto-Detection", {
            "fields": ("icon",),
            "description": "✨ <b>Auto-Fetch Enabled</b>: If left blank, saving will automatically find the matching icon from <i>Devicon</i>, <i>SimpleIcons</i>, or <i>SkillIcons</i>. You can also upload a custom icon anytime."
        }),
        ("Certificates & Resources", {
            "fields": ("certificate", "resource_links"),
            "classes": ("collapse",)
        }),
    )

    def icon_preview(self, obj):
        if obj.icon:
            return format_html('<div style="width:34px; height:34px; display:flex; align-items:center; justify-content:center; background:rgba(255,255,255,0.06); border:1px solid #334155; border-radius:6px; padding:3px;"><img src="{}" style="max-width:28px; max-height:28px; object-fit:contain;" /></div>', obj.icon.url)
        return format_html('<span style="font-size:16px;">⚡</span>')
    icon_preview.short_description = "Icon"

    def level_bar(self, obj):
        color = "#34d399" if obj.level >= 80 else ("#60a5fa" if obj.level >= 50 else "#f59e0b")
        return format_html(
            '<div style="display:flex; align-items:center; gap:8px; width:120px;">'
            '<div style="flex:1; height:6px; background:#1e293b; border-radius:3px; overflow:hidden;">'
            '<div style="width:{}%; height:100%; background:{}; border-radius:3px;"></div>'
            '</div>'
            '<span style="font-size:12px; font-weight:600; color:#e2e8f0;">{}%</span>'
            '</div>',
            obj.level, color, obj.level
        )
    level_bar.short_description = "Proficiency"

    def status_badge(self, obj):
        colors = {
            "Expert": ("rgba(16, 185, 129, 0.15)", "#34d399", "rgba(16, 185, 129, 0.35)"),
            "Learning": ("rgba(59, 130, 246, 0.15)", "#60a5fa", "rgba(59, 130, 246, 0.35)"),
            "Average": ("rgba(245, 158, 11, 0.15)", "#fbbf24", "rgba(245, 158, 11, 0.35)")
        }
        bg, text, border = colors.get(obj.status, ("rgba(255,255,255,0.1)", "#ffffff", "#475569"))
        return format_html(
            '<span style="display:inline-block; padding:3px 9px; background:{}; color:{}; border:1px solid {}; border-radius:4px; font-size:11.5px; font-weight:600;">{}</span>',
            bg, text, border, obj.status
        )
    status_badge.short_description = "Status"

    def category_badges(self, obj):
        cats = obj.get_category_list()
        badges = [f'<span style="display:inline-block; padding: 2px 7px; margin: 1px; background: rgba(99,102,241,0.18); border: 1px solid rgba(99,102,241,0.35); border-radius: 4px; font-size: 11px; color: #a5b4fc;">{c}</span>' for c in cats]
        return mark_safe(" ".join(badges)) if badges else "-"
    category_badges.short_description = "Categories"


@admin.register(Experience)
class ExperienceAdmin(admin.ModelAdmin):
    list_display = ("company_logo", "title", "date_range", "category_badges")
    list_filter = ("start_date", "end_date", "categories")
    search_fields = ("title", "description", "categories")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            is_current=models.Case(
                models.When(end_date__isnull=True, then=models.Value(1)),
                default=models.Value(0),
                output_field=models.IntegerField()
            )
        ).order_by("-is_current", "-start_date")

    def company_logo(self, obj):
        if obj.image:
            return format_html('<div style="width:34px; height:34px; display:flex; align-items:center; justify-content:center; background:rgba(255,255,255,0.06); border:1px solid #334155; border-radius:6px; padding:3px;"><img src="{}" style="max-width:28px; max-height:28px; object-fit:contain;" /></div>', obj.image.url)
        return format_html('<span style="font-size:16px;">🏢</span>')
    company_logo.short_description = "Logo"

    def date_range(self, obj):
        start = obj.start_date.strftime("%b %Y") if obj.start_date else ""
        end = obj.end_date.strftime("%b %Y") if obj.end_date else "Present"
        return format_html('<span style="color:#cbd5e1;">{} – {}</span>', start, end)
    date_range.short_description = "Duration"

    def category_badges(self, obj):
        cats = obj.get_category_list()
        badges = [f'<span style="display:inline-block; padding: 2px 7px; margin: 1px; background: rgba(99,102,241,0.18); border: 1px solid rgba(99,102,241,0.35); border-radius: 4px; font-size: 11px; color: #a5b4fc;">{c}</span>' for c in cats]
        return mark_safe(" ".join(badges)) if badges else "-"
    category_badges.short_description = "Categories"


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("question", "category_badges", "created_at")
    list_filter = ("categories", "created_at")
    search_fields = ("question", "answer")

    def has_add_permission(self, request):
        if FAQ.objects.count() >= 6:
            return False
        return super().has_add_permission(request)

    def category_badges(self, obj):
        cats = obj.get_category_list()
        badges = [f'<span style="display:inline-block; padding: 2px 7px; margin: 1px; background: rgba(99,102,241,0.18); border: 1px solid rgba(99,102,241,0.35); border-radius: 4px; font-size: 11px; color: #a5b4fc;">{c}</span>' for c in cats]
        return mark_safe(" ".join(badges)) if badges else "-"
    category_badges.short_description = "Categories"


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "subject", "ip_address", "created_at")
    list_filter = ("created_at",)
    search_fields = ("name", "email", "subject", "message")
    readonly_fields = ("created_at", "ip_address")

