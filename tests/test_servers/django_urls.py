from app.models import Article
from django.urls import path
import json
from django.http.response import HttpResponse


def get_article(request):
    return HttpResponse(
        json.dumps(list(Article.objects.filter(id=request.GET.get('id')).values()))
    )


urlpatterns = [
    path('article', get_article)
]
