from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.template.defaultfilters import date
from unrest_comments.models import UnrestComment

import markdown

def ajax_login_required(function):
  def wrap(request,*args,**kwargs):
    if not request.user.is_authenticated():
      response = HttpResponse("Unauthorized: You must be logged in to do that.")
      response.status_code = 401
      return response
    return function(request,*args,**kwargs)
  wrap.csrf_exempt = True
  return wrap

def build_comment_json(comment):
  children = comment.get_children().order_by("-submit_date") # this should eventually be on UnrestComment.Meta
  return {
    'pk': comment.pk,
    'comments': [build_comment_json(c) for c in children],
    'username': comment.user.username if comment.user else None,
    'user_pk': comment.user_id,
    'date_s': date(comment.submit_date,r"l F j, Y \a\t P"),
    'comment': comment.comment,
    'rendered': comment.rendered,
    'level': comment.level,
    'l_mod': comment.level%2,
  }

def detail(request,pk):
  comment = get_object_or_404(UnrestComment,pk=pk)
  ct = comment.content_type
  x = dir(ct)
  d = build_comment_json(comment)
  d['content_type'] = "%s.%s"%(ct.app_label,ct.name)
  d['object_pk'] = comment.object_pk
  return JsonResponse(d)

def list_comments(request):
  natural_key = request.GET.get('content_type').split('.')
  comments = UnrestComment.objects.filter(
    object_pk=request.GET['object_pk'],
    content_type=ContentType.objects.get_by_natural_key(*natural_key),
    parent=None
  ).order_by("-submit_date") # this should eventually be on UnrestComment.Meta
  comments_json = [build_comment_json(c) for c in comments]
  return JsonResponse(comments_json,safe=False)

#! TODO most of this function should be a shared form with edit
@ajax_login_required
def post(request):
  parent_pk = request.POST.get("parent_pk",None)
  if parent_pk:
    parent = get_object_or_404(UnrestComment,pk=parent_pk)
    content_type = parent.content_type
    object_pk = parent.object_pk
  else:
    parent = None
    natural_key = request.POST.get('content_type').split('.')
    content_type = ContentType.objects.get_by_natural_key(*natural_key)
    object_pk = request.POST.get('object_pk')
  comment = UnrestComment.objects.create(
    user=request.user,
    content_type=content_type,
    object_pk=object_pk,
    parent=parent,
    comment=request.POST.get('comment'),
    site=get_current_site(request),
    ip_address=request.META.get("REMOTE_ADDR", None),
  )
  return JsonResponse(build_comment_json(comment))

@ajax_login_required
def edit(request,pk):
  comment = get_object_or_deny(UnrestComment,request.user,pk=pk)
  if request.POST:
    comment.comment = request.POST['comment']
    comment.save()
  return JsonResponse(build_comment_json(comment))

def get_object_or_deny(model,user_object,*args,**kwargs):
  obj = get_object_or_404(model,*args,**kwargs)
  if not (user_object.is_superuser or user_object == obj.user):
    raise PermissionDenied()
  return obj

#! TODO Not implimented
@ajax_login_required
def delete(request,pk):
  comment = get_object_or_deny(UnrestComment,user,pk=pk)
  comment.is_removed = True
  comment.save()
  JsonResponse({'message': "You have deleted this Comment."})

#! TODO Not implimented
@ajax_login_required
def flag(request,pk):
  comment = get_object_or_deny(UnrestComment,user,pk=pk)
  comment.is_flagged = True
  comment.save()
  JsonResponse({'message': "This comment has been flagged and will be reviewed."})
