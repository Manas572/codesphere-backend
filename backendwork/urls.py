print("is loading urls.py")
from django.contrib import admin
from django.urls import path
from handle import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('execute/',views.ExecuteCodeAPIView.as_view() ),
    path('TC/',views.FTC.as_view() ),
    path('chatbot/',views.CB.as_view() ),
    path('vis/',views.Visual.as_view()),
    path('info/', views.Han.as_view()),
    path('sub/', views.Subinfo.as_view()),
    path('con/', views.Contestinfo.as_view()),
]
