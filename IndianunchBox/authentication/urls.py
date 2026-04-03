from django.urls import path
from . import views

urlpatterns = [
    # Main pages
    path('', views.home, name='home'),
    path('about/', views.about_view, name='about'),  # About page route
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('contact/', views.contact_view, name='contact'),
    # Add these to your existing urls.py
    
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('reset-password/<str:token>/', views.reset_password, name='reset_password'),
    path('api/forgot-password/', views.api_forgot_password, name='api_forgot_password'),
    
    # Recipe CRUD
    path('add-recipe/', views.add_recipe, name='add_recipe'),
    path('recipes/', views.view_recipes, name='view_recipes'),
    path('recipe/<int:id>/', views.recipe_detail, name='recipe_detail'),
    path('recipe/<int:id>/download/', views.download_recipe_pdf, name='download_pdf'),
    
    # User pages
    # Add these to your urls.py
    
    path('my-recipes/', views.my_recipes, name='my_recipes'),
    path('saved-recipes/', views.saved_recipes, name='saved_recipes'),
    path('my-profile/', views.user_profile, name='user_profile'),
    path('update-profile/', views.update_profile, name='update_profile'),
    path('api/recipe/<int:recipe_id>/delete/', views.delete_recipe_api, name='delete_recipe_api'),
    path('api/saved/<int:saved_id>/remove/', views.remove_saved_api, name='remove_saved_api'),
    
    # Terms and Privacy pages
    path('terms/', views.terms_view, name='terms'),
    path('privacy/', views.privacy_view, name='privacy'),
    
    # API Endpoints (AJAX)
    # path('api/check-email/', views.api_check_email, name='api_check_email'),
    # path('api/login/', views.api_login, name='api_login'),
    path('api/recipe/<int:recipe_id>/like/', views.toggle_like, name='toggle_like'),
    # path('api/recipe/<int:recipe_id>/rate/', views.api_add_rating, name='api_add_rating'),
    # path('api/recipe/<int:recipe_id>/save/', views.api_save_recipe, name='api_save_recipe'),
]