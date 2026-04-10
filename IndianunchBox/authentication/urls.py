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
    
    
    # Add these to your existing urlpatterns
    
    # Favorites routes
    path('favorites/', views.favorites, name='favorites'),
    path('api/favorite/<int:recipe_id>/remove/', views.remove_favorite_api, name='remove_favorite_api'),
    
    # My Reviews routes
    path('my-reviews/', views.my_reviews, name='my_reviews'),
    path('edit-review/<int:comment_id>/', views.edit_review, name='edit_review'),
    path('api/review/<int:comment_id>/delete/', views.delete_review_api, name='delete_review_api'),
    
    # Settings routes
    path('settings/', views.settings_view, name='settings'),
    path('update-account/', views.update_account_settings, name='update_account_settings'),
    path('update-preferences/', views.update_preferences, name='update_preferences'),
    path('delete-account/', views.delete_account, name='delete_account'),
    
    # API Endpoints (AJAX)
    # path('api/check-email/', views.api_check_email, name='api_check_email'),
    # path('api/login/', views.api_login, name='api_login'),
    path('api/recipe/<int:recipe_id>/like/', views.toggle_like, name='toggle_like'),
    # path('api/recipe/<int:recipe_id>/rate/', views.api_add_rating, name='api_add_rating'),
    # path('api/recipe/<int:recipe_id>/save/', views.api_save_recipe, name='api_save_recipe'),
    # Add these to your urlpatterns
    path('api/save-recipe/', views.api_save_recipe, name='api_save_recipe'),
    path('api/get-saved-recipes/', views.api_get_saved_recipes, name='api_get_saved_recipes'),
    path('api/add-rating/', views.api_add_rating, name='api_add_rating'),
   
   
   
   # Add these to your urlpatterns
   path('api/get-saved-count/', views.api_get_saved_count, name='api_get_saved_count'),
   path('api/save-recipe/', views.api_save_recipe, name='api_save_recipe'),
  
  
  # Add these to your urlpatterns
  path('api/toggle-like/', views.api_toggle_like, name='api_toggle_like'),
  path('api/add-comment/', views.api_add_comment, name='api_add_comment'),
  path('api/delete-comment/', views.api_delete_comment, name='api_delete_comment'),
 
 
 # Add these to your urlpatterns
 path('api/toggle-comment-like/', views.api_toggle_comment_like, name='api_toggle_comment_like'),
 path('api/add-reply/', views.api_add_reply, name='api_add_reply'),
 path('api/get-replies/<int:comment_id>/', views.api_get_replies, name='api_get_replies'),
 path('api/toggle-reply-like/', views.api_toggle_reply_like, name='api_toggle_reply_like'),
 path('api/delete-reply/', views.api_delete_reply, name='api_delete_reply'), 
 
 
 # Add these to your urlpatterns
 
 # Lunchbox Stories URLs
 path('lunchbox-stories/', views.lunchbox_stories, name='lunchbox_stories'),
 path('story/<int:id>/', views.story_detail, name='story_detail'),
 path('add-story/', views.add_story, name='add_story'),
 path('edit-story/<int:id>/', views.edit_story, name='edit_story'),
 path('delete-story/<int:id>/', views.delete_story, name='delete_story'),
 path('my-stories/', views.my_stories, name='my_stories'),
 
 # API Endpoints for Stories
 path('api/story/<int:id>/like/', views.toggle_story_like, name='toggle_story_like'),
 path('api/story/<int:id>/comment/', views.add_story_comment, name='add_story_comment'),
 path('api/story/delete-comment/<int:comment_id>/', views.delete_story_comment, name='delete_story_comment'),
]