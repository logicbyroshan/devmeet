from django.shortcuts import render, get_object_or_404
from .models import Project, Blog, Skill, Experience, FAQ, Resume, ContactMessage
from django.core.paginator import Paginator
from django.db.models import Q, Case, When, Value, IntegerField, F
from django.core.mail import send_mail
from django.http import JsonResponse, FileResponse, HttpResponse
from django.conf import settings
import logging
import os
from django.utils import timezone

logger = logging.getLogger(__name__)

def get_client_ip(request):
    """Safely extract the real client IP from HTTP headers"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
    return ip

def handle_contact_submission(request):
    """Handle contact form submission and save to database with IP rate limiting"""
    try:
        client_ip = get_client_ip(request)
        today = timezone.now() - timezone.timedelta(days=1)
        
        recent_submissions = ContactMessage.objects.filter(
            ip_address=client_ip, 
            created_at__gte=today
        ).count()
        
        max_allowed = 100 if settings.DEBUG else 10
        if recent_submissions >= max_allowed:
            return JsonResponse({
                "success": False, 
                "error": "You have reached the maximum number of contact requests for today. Please try again later."
            }, status=429)

        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        subject = request.POST.get("subject", "").strip()
        message = request.POST.get("message", "").strip()

        # Validate required fields
        if not all([name, email, subject, message]):
            return JsonResponse({
                "success": False, 
                "error": "All fields are required."
            }, status=400)

        # Save to database
        contact_message = ContactMessage.objects.create(
            name=name[:100],
            email=email[:254],
            subject=subject[:255],
            message=message[:5000],
            ip_address=client_ip
        )

        # Send notification email if configured
        try:
            send_mail(
                subject=f"New Contact Form: {subject}",
                message=f"From: {name} ({email})\nIP: {client_ip}\n\nMessage:\n{message}",
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'contact@roshandamor.site'),
                recipient_list=[getattr(settings, 'DEFAULT_FROM_EMAIL', 'contact@roshandamor.site')],
                fail_silently=True,
            )
            logger.info(f"Email sent successfully for contact ID: {contact_message.id}")
        except Exception as email_error:
            logger.warning(f"Email sending failed but contact saved: {email_error}")

        return JsonResponse({
            "success": True,
            "message": "Your message has been sent successfully! I'll get back to you soon."
        })
        
    except Exception as e:
        logger.error(f"Contact form submission failed: {e}")
        return JsonResponse({
            "success": False, 
            "error": "Something went wrong. Please try again later."
        }, status=500)


def latest_resume(request):
    try:
        latest = Resume.objects.order_by("-uploaded_at").first()
    except Exception:
        latest = None
    return {"resume": latest}


def get_resume(request):
    try:
        latest = Resume.objects.order_by("-uploaded_at").first()
        if latest and latest.file:
            if hasattr(latest.file, 'path') and os.path.exists(latest.file.path):
                return FileResponse(
                    latest.file.open(),
                    content_type='application/pdf',
                    headers={'Content-Disposition': 'inline; filename="Roshan_Damor_Resume.pdf"'}
                )
    except Exception as e:
        logger.error(f"Failed to retrieve resume: {e}")
    return HttpResponse("No resume found", status=404)


def download_resume(request):
    try:
        latest = Resume.objects.order_by("-uploaded_at").first()
        if latest and latest.file:
            if hasattr(latest.file, 'path') and os.path.exists(latest.file.path):
                filename = os.path.basename(latest.file.name) or "Roshan_Damor_Resume.pdf"
                return FileResponse(latest.file.open(), as_attachment=True, filename=filename)
    except Exception as e:
        logger.error(f"Failed to download resume: {e}")
    return HttpResponse("No resume available", status=404)


def user_terms_view(request):
    return render(request, "user-terms.html")


def get_unique_categories(queryset, field_name):
    """Extract unique categories from a given model field optimally."""
    categories = set()
    raw_cats = queryset.exclude(**{f"{field_name}__isnull": True}).exclude(**{f"{field_name}__exact": ""}).values_list(field_name, flat=True)
    for obj in raw_cats:
        for cat in obj.split(","):
            clean_cat = cat.strip()
            if clean_cat and clean_cat.lower() != "uncategorized":
                categories.add(clean_cat)
    return sorted(categories)


def home(request):
    if request.method == "POST" and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return handle_contact_submission(request)
    
    sort_by = request.GET.get("sort", "latest").strip()
    category = request.GET.get("category", "").strip()

    # Optimized prefetching
    projects = Project.objects.prefetch_related("images", "skills").all()
    blogs = Blog.objects.all()
    skills = Skill.objects.all()
    experiences = Experience.objects.all()
    faqs = FAQ.objects.all()

    if category:
        projects = projects.filter(categories__icontains=category)
        blogs = blogs.filter(categories__icontains=category)
        skills = skills.filter(categories__icontains=category)
        experiences = experiences.filter(categories__icontains=category)
        faqs = faqs.filter(categories__icontains=category)

    if sort_by == 'oldest':
        projects = projects.order_by('created_at')[:3]
        blogs = blogs.order_by('created_at')[:3]
    elif sort_by in ['-publication_date', 'publication_date']:
        projects = projects.order_by(sort_by)[:3]
        blogs = blogs.order_by(sort_by)[:3]
    else:  # latest (default)
        projects = projects.order_by('-created_at')[:3]
        blogs = blogs.order_by('-created_at')[:3]

    skills = skills.order_by("-level", "-created_at")[:6]
    experiences = experiences.annotate(
        is_current=Case(
            When(end_date__isnull=True, then=Value(1)),
            default=Value(0),
            output_field=IntegerField()
        )
    ).order_by("-is_current", "-start_date", "-created_at")[:3]
    faqs = faqs.order_by("-created_at")[:6]

    return render(request, "portfolio-landing-page.html", {
        "projects": projects,
        "blogs": blogs,
        "skills": skills,
        "experiences": experiences,
        "faqs": faqs,
        "selected_category": category,
        "selected_sort": sort_by,
    })


def project_detail(request, slug):
    project = get_object_or_404(Project.objects.prefetch_related('images', 'features', 'learnings', 'skills'), slug=slug)

    category_list = project.get_category_list()
    similar_query = Q()
    for cat in category_list:
        similar_query |= Q(categories__icontains=cat)

    if category_list:
        similar_projects = Project.objects.prefetch_related("images", "skills").filter(similar_query).exclude(id=project.id)[:3]
    else:
        similar_projects = Project.objects.none()

    latest_projects = Project.objects.prefetch_related("images", "skills").exclude(id=project.id).order_by('-created_at')[:3]

    return render(request, 'project-detail.html', {
        'project': project,
        'similar_projects': similar_projects,
        'latest_projects': latest_projects
    })


def blog_detail(request, slug):
    blog = get_object_or_404(Blog, slug=slug)

    category_list = blog.get_category_list()
    similar_query = Q()
    for cat in category_list:
        similar_query |= Q(categories__icontains=cat)

    if category_list:
        similar_blogs = Blog.objects.filter(similar_query).exclude(id=blog.id)[:3]
    else:
        similar_blogs = Blog.objects.none()

    latest_blogs = Blog.objects.exclude(id=blog.id).order_by('-created_at')[:3]

    return render(request, 'blog-detail.html', {
        'blog': blog,
        'similar_blogs': similar_blogs,
        'latest_blogs': latest_blogs
    })


# Project Views
def project_list(request):
    query = request.GET.get('search', '').strip()
    category = request.GET.get('category', '').strip()
    sort_by = request.GET.get('sort', 'latest').strip()

    projects = Project.objects.prefetch_related('images', 'skills').all()
    category_list = get_unique_categories(Project.objects, "categories")

    if query:
        projects = projects.filter(
            Q(title__icontains=query) | 
            Q(description__icontains=query) |
            Q(categories__icontains=query) |
            Q(tags__icontains=query)
        ).distinct()

    if category and category != "all":  
        projects = projects.filter(categories__icontains=category)

    if sort_by == 'oldest':
        projects = projects.order_by('created_at')
    else:  # latest
        projects = projects.order_by('-created_at')

    # Pagination: 9 per page
    paginator = Paginator(projects, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'projects.html', {
        'projects': page_obj, 
        'page_obj': page_obj,
        'query': query, 
        'selected_category': category, 
        'sort': sort_by, 
        'category_list': category_list
    })


# Blog Views
def blog_list(request):
    query = request.GET.get('search', '').strip()
    category = request.GET.get('category', '').strip()
    sort_by = request.GET.get('sort', 'latest').strip()

    blogs = Blog.objects.all()
    category_list = get_unique_categories(Blog.objects, "categories")

    if query:
        blogs = blogs.filter(
            Q(title__icontains=query) | 
            Q(content__icontains=query) |
            Q(categories__icontains=query)
        ).distinct()

    if category and category != "all":  
        blogs = blogs.filter(categories__icontains=category)

    if sort_by == 'oldest':
        blogs = blogs.order_by('publication_date')
    else:  # latest
        blogs = blogs.order_by('-publication_date')

    # Pagination: 9 per page
    paginator = Paginator(blogs, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'blogs.html', {
        'blogs': page_obj, 
        'page_obj': page_obj,
        'query': query, 
        'selected_category': category, 
        'sort': sort_by, 
        'category_list': category_list
    })


# Skill Views
def skill_list(request):
    query = request.GET.get('search', '').strip()
    category = request.GET.get('category', '').strip()
    sort_by = request.GET.get('sort', 'latest').strip()

    skills = Skill.objects.all()
    category_list = get_unique_categories(Skill.objects, "categories")

    if query:
        skills = skills.filter(
            Q(name__icontains=query) | 
            Q(description__icontains=query) |
            Q(categories__icontains=query)
        ).distinct()

    if category and category != "all":  
        skills = skills.filter(categories__icontains=category)

    if sort_by == 'oldest':
        skills = skills.order_by('created_at')
    elif sort_by == 'level':
        skills = skills.order_by('-level', 'name')
    elif sort_by == 'name':
        skills = skills.order_by('name')
    else:  # latest
        skills = skills.order_by('-created_at')

    # Pagination: 15 per page
    paginator = Paginator(skills, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'skills.html', {
        'skills': page_obj, 
        'page_obj': page_obj,
        'query': query, 
        'selected_category': category, 
        'sort': sort_by, 
        'category_list': category_list
    })


# Experience Views
def experience_list(request):
    query = request.GET.get('search', '').strip()
    category = request.GET.get('category', '').strip()
    sort_by = request.GET.get('sort', '-start_date').strip()

    experiences = Experience.objects.all()
    category_list = get_unique_categories(Experience.objects, "categories")

    if query:
        experiences = experiences.filter(
            Q(title__icontains=query) | 
            Q(description__icontains=query) | 
            Q(categories__icontains=query)
        ).distinct()

    if category and category != "all":  
        experiences = experiences.filter(categories__icontains=category)

    if sort_by == 'oldest':
        experiences = experiences.order_by('start_date')
    else:
        experiences = experiences.annotate(
            is_current=Case(
                When(end_date__isnull=True, then=Value(1)),
                default=Value(0),
                output_field=IntegerField()
            )
        ).order_by("-is_current", "-start_date", "-created_at")

    paginator = Paginator(experiences, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'experiences.html', {
        'experiences': page_obj, 
        'page_obj': page_obj,
        'query': query, 
        'selected_category': category, 
        'sort': sort_by, 
        'category_list': category_list
    })





# Custom HTTP Error Handlers
def custom_404_view(request, exception=None):
    return render(request, "404.html", status=404)

def custom_500_view(request):
    return render(request, "500.html", status=500)

def custom_403_view(request, exception=None):
    return render(request, "403.html", status=403)

def custom_400_view(request, exception=None):
    return render(request, "400.html", status=400)


def skill_icon_lookup(request):
    """
    API endpoint for admin panel live icon discovery and preview.
    Queries 3-tier fallback icon CDNs (Devicon, SimpleIcons, SkillIcons).
    """
    name = request.GET.get("name", "").strip()
    if not name:
        return JsonResponse({"found": False, "error": "Name is required"})
    
    from .icon_fetcher import fetch_skill_icon, normalize_skill_name
    content, source, url = fetch_skill_icon(name)
    normalized = normalize_skill_name(name)

    if url:
        return JsonResponse({
            "found": True,
            "name": name,
            "normalized": normalized,
            "source": source,
            "url": url,
        })
    else:
        return JsonResponse({
            "found": False,
            "name": name,
            "normalized": normalized,
            "source": None,
            "url": None,
        })


