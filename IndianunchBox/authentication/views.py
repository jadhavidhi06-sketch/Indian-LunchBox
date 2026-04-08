from django.shortcuts import render, redirect
from django.core.files.storage import FileSystemStorage
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.template.loader import get_template
from django.contrib import messages
from xhtml2pdf import pisa
import hashlib
import json
import random
import string
from datetime import datetime, timedelta
import os
from django.conf import settings
from xhtml2pdf.default import DEFAULT_CSS
# ==============================================
# HASH PASSWORD FUNCTION
# ==============================================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# ==============================================
# HOME PAGE VIEW
# ==============================================
def home(request):
    if not request.session.get('user_id'):
        return redirect('login')

    # Fetch all recipes (latest first)
    with connection.cursor() as cursor:
        cursor.execute("SELECT recipe_id, title, description, image FROM recipes ORDER BY recipe_id DESC")
        recipes = cursor.fetchall()  # List of tuples

    return render(request, 'home.html', {'recipes': recipes})


# ==============================================
# REGISTER VIEW
# ==============================================
def register_view(request):
    if request.method == "POST":
        name = request.POST['name']
        email = request.POST['email']
        password = hash_password(request.POST['password'])

        with connection.cursor() as cursor:
            cursor.callproc('RegisterUser', [name, email, password])

        return redirect('login')

    return render(request, 'auth/register.html')


# ==============================================
# LOGIN VIEW
# ==============================================
def login_view(request):
    if request.method == "POST":
        email = request.POST['email']
        password = hash_password(request.POST['password'])

        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE email=%s", [email])
            user = cursor.fetchone()

        if user and user[3] == password:
            request.session['user_id'] = user[0]
            request.session['user_name'] = user[1]
            return redirect('home')
        else:
            return HttpResponse("Invalid credentials")

    return render(request, 'auth/login.html')


# ==============================================
# LOGOUT VIEW
# ==============================================
def logout_view(request):
    request.session.flush()
    return redirect('login')


# ==============================================
# ADD RECIPE VIEW
# ==============================================
def add_recipe(request):
    if not request.session.get('user_id'):
        return redirect('login')

    if request.method == "POST":
        title = request.POST['title']
        description = request.POST['description']
        ingredients = request.POST['ingredients']
        steps = request.POST['steps']

        # Handle image upload
        image = request.FILES.get('image')
        fs = FileSystemStorage()
        filename = fs.save(image.name, image)

        # Save recipe via procedure
        with connection.cursor() as cursor:
            cursor.callproc('AddRecipe', [
                request.session['user_id'],
                title,
                description,
                ingredients,
                steps,
                filename
            ])
        return redirect('view_recipes')

    return render(request, 'recipes/add_recipe.html')


# ==============================================
# VIEW RECIPES PAGE (FEED)
# ==============================================
def view_recipes(request):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT r.recipe_id, r.title, r.description, r.image, u.name
            FROM recipes r
            JOIN users u ON r.user_id = u.user_id
            ORDER BY r.recipe_id DESC
        """)
        recipes = cursor.fetchall()
    return render(request, 'recipes/view_recipes.html', {'recipes': recipes})


# ==============================================
# RECIPE DETAIL + COMMENTS
# ==============================================
def recipe_detail(request, id):
    # Fetch recipe
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT r.recipe_id, r.title, r.description, r.ingredients, r.steps, r.image, u.name
            FROM recipes r
            JOIN users u ON r.user_id = u.user_id
            WHERE r.recipe_id=%s
        """, [id])
        recipe = cursor.fetchone()

    # Fetch comments
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT c.comment_id, c.comment, c.rating, u.name
            FROM comments c
            JOIN users u ON c.user_id = u.user_id
            WHERE c.recipe_id=%s
            ORDER BY c.comment_id DESC
        """, [id])
        comments = cursor.fetchall()

    # Add comment
    if request.method == "POST" and request.session.get('user_id'):
        comment_text = request.POST['comment']
        rating = int(request.POST['rating'])
        with connection.cursor() as cursor:
            cursor.callproc('AddComment', [id, request.session['user_id'], comment_text, rating])
        return redirect(f'/recipe/{id}/')

    return render(request, 'recipes/recipe_detail.html', {
        'recipe': recipe,
        'comments': comments
    })


# ==============================================
# DOWNLOAD RECIPE AS PDF
# ==============================================

from django.shortcuts import render
from django.db import connection
from django.http import HttpResponse
from django.template.loader import render_to_string
from weasyprint import HTML
import os
from django.conf import settings
from datetime import datetime
import re


def download_recipe_pdf(request, id):

    # FETCH DATA
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT r.title, r.description, r.ingredients, r.steps, r.image, u.name, r.recipe_id
            FROM recipes r
            JOIN users u ON r.user_id = u.user_id
            WHERE r.recipe_id=%s
        """, [id])
        recipe_data = cursor.fetchone()

    if not recipe_data:
        return HttpResponse("Recipe not found", status=404)

    title, description, ingredients, steps, image, author_name, recipe_id = recipe_data

    # IMAGE PATH (important for WeasyPrint)
    image_url = None
    if image:
        image_url = request.build_absolute_uri(settings.MEDIA_URL + image)

    # EXTRA DATA
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM likes WHERE recipe_id=%s", [id])
        likes_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM comments WHERE recipe_id=%s", [id])
        comments_count = cursor.fetchone()[0]

        cursor.execute("SELECT AVG(rating) FROM comments WHERE recipe_id=%s AND rating > 0", [id])
        avg_rating = cursor.fetchone()[0]
        avg_rating = round(avg_rating, 1) if avg_rating else 0

    total_words = len((description or "").split()) + len((ingredients or "").split()) + len((steps or "").split())
    read_time = max(1, round(total_words / 200))

    context = {
        'recipe': {
            'title': title,
            'description': description,
            'ingredients': ingredients,
            'steps': steps,
            'author_name': author_name,
        },
        'image_url': image_url,
        'download_date': datetime.now().strftime("%B %d, %Y"),
        'likes_count': likes_count,
        'comments_count': comments_count,
        'avg_rating': avg_rating,
        'read_time': read_time,
    }

    # RENDER HTML
    html_string = render_to_string('recipes/recipe_pdf.html', context)

    # GENERATE PDF
    pdf = HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()

    # RESPONSE
    response = HttpResponse(pdf, content_type='application/pdf')
    filename = re.sub(r'[^\w\s-]', '', title)[:50]
    response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'

    return response


# ==============================================
# TOGGLE LIKE (AJAX)
# ==============================================
def toggle_like(request, recipe_id):
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'error': 'Not logged in'}, status=401)

    with connection.cursor() as cursor:
        # Check if already liked
        cursor.execute("SELECT * FROM likes WHERE recipe_id=%s AND user_id=%s", [recipe_id, user_id])
        existing = cursor.fetchone()
        if existing:
            cursor.execute("DELETE FROM likes WHERE recipe_id=%s AND user_id=%s", [recipe_id, user_id])
            liked = False
        else:
            cursor.execute("INSERT INTO likes(recipe_id, user_id) VALUES(%s,%s)", [recipe_id, user_id])
            liked = True
    return JsonResponse({'liked': liked})


# ==============================================
# ABOUT PAGE
# ==============================================
def about_view(request):
    """
    About page view - tells the story of IndianLunchBox
    """
    return render(request, 'about.html')


# ==============================================
# TERMS OF SERVICE PAGE
# ==============================================
def terms_view(request):
    """
    Terms of Service page
    """
    return render(request, 'auth/terms.html')


# ==============================================
# PRIVACY POLICY PAGE
# ==============================================
def privacy_view(request):
    """
    Privacy Policy page
    """
    return render(request, 'auth/privacy.html')


# ==============================================
# CONTACT PAGE
# ==============================================
def contact_view(request):
    """
    Contact page view
    """
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        # Basic validation
        if not name or not email or not subject or not message:
            messages.error(request, 'Please fill in all fields.')
            return render(request, 'contact.html')
        
        if len(message) < 10:
            messages.error(request, 'Message must be at least 10 characters.')
            return render(request, 'contact.html')
        
        # Save to database
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO contact_messages (name, email, subject, message, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                """, [name, email, subject, message])
        except:
            # Table might not exist, just skip saving
            pass
        
        messages.success(request, f'Thank you {name}! Your message has been sent. We\'ll get back to you soon. ❤️')
        return redirect('contact')
    
    return render(request, 'contact.html')


# ==============================================
# FORGOT PASSWORD PAGE
# ==============================================
def forgot_password(request):
    """
    Forgot password page view
    """
    if request.method == 'POST':
        email = request.POST.get('email')
        
        with connection.cursor() as cursor:
            # Check if email exists
            cursor.execute("SELECT user_id, name FROM users WHERE email = %s", [email])
            user = cursor.fetchone()
        
        if user:
            # Generate reset token
            reset_token = ''.join(random.choices(string.ascii_letters + string.digits, k=64))
            
            # Store token in session
            request.session['reset_token'] = reset_token
            request.session['reset_email'] = email
            request.session['reset_expiry'] = (datetime.now() + timedelta(minutes=30)).timestamp()
            
            messages.success(request, f'Password reset link sent to {email}. Please check your inbox.')
        else:
            messages.error(request, 'No account found with this email address.')
        
        return redirect('forgot_password')
    
    return render(request, 'auth/forgot_password.html')


# ==============================================
# API: FORGOT PASSWORD (AJAX)
# ==============================================
def api_forgot_password(request):
    """
    API endpoint for forgot password (AJAX)
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email')
            
            if not email:
                return JsonResponse({
                    'success': False,
                    'error': 'missing_email',
                    'message': 'Email is required'
                }, status=400)
            
            with connection.cursor() as cursor:
                cursor.execute("SELECT user_id, name FROM users WHERE email = %s", [email])
                user = cursor.fetchone()
            
            if user:
                # Generate reset token
                reset_token = ''.join(random.choices(string.ascii_letters + string.digits, k=64))
                
                # Store token in session
                request.session['reset_token'] = reset_token
                request.session['reset_email'] = email
                request.session['reset_expiry'] = (datetime.now() + timedelta(minutes=30)).timestamp()
                
                return JsonResponse({
                    'success': True,
                    'message': 'Reset link sent successfully'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'email_not_found',
                    'message': 'Email not registered'
                }, status=404)
                
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'invalid_json',
                'message': 'Invalid request format'
            }, status=400)
    
    return JsonResponse({
        'success': False,
        'error': 'invalid_method',
        'message': 'Invalid request method'
    }, status=405)


# ==============================================
# RESET PASSWORD PAGE
# ==============================================
def reset_password(request, token):
    """
    Reset password page - called from email link
    """
    # Check if token is valid
    session_token = request.session.get('reset_token')
    reset_email = request.session.get('reset_email')
    reset_expiry = request.session.get('reset_expiry')
    
    if not session_token or session_token != token or not reset_expiry:
        messages.error(request, 'Invalid or expired reset link. Please try again.')
        return redirect('forgot_password')
    
    # Check if token expired
    if datetime.now().timestamp() > reset_expiry:
        messages.error(request, 'Reset link has expired. Please request a new one.')
        return redirect('forgot_password')
    
    if request.method == 'POST':
        new_password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        if not new_password or len(new_password) < 6:
            messages.error(request, 'Password must be at least 6 characters')
            return render(request, 'auth/reset_password.html', {'token': token})
        
        if new_password != confirm_password:
            messages.error(request, 'Passwords do not match')
            return render(request, 'auth/reset_password.html', {'token': token})
        
        # Update password
        hashed_password = hash_password(new_password)
        with connection.cursor() as cursor:
            cursor.execute("UPDATE users SET password = %s WHERE email = %s", [hashed_password, reset_email])
        
        # Clear reset session data
        request.session.pop('reset_token', None)
        request.session.pop('reset_email', None)
        request.session.pop('reset_expiry', None)
        
        messages.success(request, 'Password reset successful! Please login with your new password.')
        return redirect('login')
    
    return render(request, 'auth/reset_password.html', {'token': token})


# ==============================================
# MY RECIPES PAGE
# ==============================================
def my_recipes(request):
    """
    Display all recipes created by the logged-in user
    """
    if not request.session.get('user_id'):
        messages.error(request, 'Please login to view your recipes')
        return redirect('login')
    
    user_id = request.session['user_id']
    recipe_list = []
    
    with connection.cursor() as cursor:
        try:
            # Try using stored procedure first
            cursor.callproc('GetUserRecipes', [user_id])
            recipes = cursor.fetchall()
        except:
            # Fallback to direct query
            cursor.execute("""
                SELECT 
                    r.recipe_id,
                    r.title,
                    r.description,
                    r.image,
                    r.created_at,
                    (SELECT COUNT(*) FROM likes l WHERE l.recipe_id = r.recipe_id) as likes_count,
                    (SELECT COUNT(*) FROM comments c WHERE c.recipe_id = r.recipe_id) as comments_count
                FROM recipes r
                WHERE r.user_id = %s
                ORDER BY r.created_at DESC
            """, [user_id])
            recipes = cursor.fetchall()
    
    # Convert to list of dictionaries
    for recipe in recipes:
        recipe_list.append({
            'recipe_id': recipe[0],
            'title': recipe[1],
            'description': recipe[2],
            'image': recipe[3],
            'created_at': recipe[4],
            'likes_count': recipe[5] if len(recipe) > 5 else 0,
            'comments_count': recipe[6] if len(recipe) > 6 else 0
        })
    
    context = {
        'recipes': recipe_list,
        'total_recipes': len(recipe_list),
        'page_title': 'My Recipes'
    }
    
    return render(request, 'recipes/my_recipes.html', context)


# ==============================================
# SAVED RECIPES PAGE
# ==============================================
def saved_recipes(request):
    """
    Display all recipes saved/bookmarked by the logged-in user
    """
    if not request.session.get('user_id'):
        messages.error(request, 'Please login to view your saved recipes')
        return redirect('login')
    
    user_id = request.session['user_id']
    saved_list = []
    
    with connection.cursor() as cursor:
        try:
            # Try using stored procedure first
            cursor.callproc('GetSavedRecipes', [user_id])
            saved_recipes = cursor.fetchall()
        except:
            # Fallback to direct query
            cursor.execute("""
                SELECT 
                    s.saved_id,
                    r.recipe_id,
                    r.title,
                    r.description,
                    r.image,
                    u.name as author_name,
                    s.saved_at,
                    (SELECT COUNT(*) FROM likes l WHERE l.recipe_id = r.recipe_id) as likes_count
                FROM saved_recipes s
                JOIN recipes r ON s.recipe_id = r.recipe_id
                JOIN users u ON r.user_id = u.user_id
                WHERE s.user_id = %s
                ORDER BY s.saved_at DESC
            """, [user_id])
            saved_recipes = cursor.fetchall()
    
    for recipe in saved_recipes:
        saved_list.append({
            'saved_id': recipe[0],
            'recipe_id': recipe[1],
            'title': recipe[2],
            'description': recipe[3],
            'image': recipe[4],
            'author_name': recipe[5],
            'saved_at': recipe[6],
            'likes_count': recipe[7] if len(recipe) > 7 else 0
        })
    
    context = {
        'saved_recipes': saved_list,
        'total_saved': len(saved_list),
        'page_title': 'Saved Recipes'
    }
    
    return render(request, 'recipes/saved_recipes.html', context)


# ==============================================
# USER PROFILE PAGE (FIXED)
# ==============================================
def user_profile(request):
    """
    Display user profile with statistics and information
    """
    if not request.session.get('user_id'):
        messages.error(request, 'Please login to view your profile')
        return redirect('login')
    
    user_id = request.session['user_id']
    user_name = request.session.get('user_name')
    
    with connection.cursor() as cursor:
        # Get user profile information
        cursor.execute("""
            SELECT u.user_id, u.name, u.email, u.created_at,
                   COALESCE(p.bio, '') as bio,
                   COALESCE(p.location, '') as location,
                   COALESCE(p.favorite_food, '') as favorite_food,
                   COALESCE(p.avatar, '') as avatar
            FROM users u
            LEFT JOIN user_profiles p ON u.user_id = p.user_id
            WHERE u.user_id = %s
        """, [user_id])
        user_data = cursor.fetchone()
        
        # Get user statistics
        try:
            cursor.callproc('GetUserStatistics', [user_id])
            stats = cursor.fetchone()
        except:
            cursor.execute("""
                SELECT 
                    (SELECT COUNT(*) FROM recipes WHERE user_id = %s) as total_recipes,
                    (SELECT COUNT(*) FROM likes l 
                     JOIN recipes r ON l.recipe_id = r.recipe_id 
                     WHERE r.user_id = %s) as total_likes_received,
                    (SELECT COUNT(*) FROM comments c 
                     JOIN recipes r ON c.recipe_id = r.recipe_id 
                     WHERE r.user_id = %s) as total_comments,
                    (SELECT COUNT(*) FROM saved_recipes WHERE user_id = %s) as total_saved,
                    (SELECT COUNT(*) FROM likes WHERE user_id = %s) as total_likes_given
            """, [user_id, user_id, user_id, user_id, user_id])
            stats = cursor.fetchone()
    
    if user_data:
        profile = {
            'user_id': user_data[0],
            'name': user_data[1],
            'email': user_data[2],
            'joined_date': user_data[3],
            'bio': user_data[4] or '',
            'location': user_data[5] or '',
            'favorite_food': user_data[6] or '',
            'avatar': user_data[7] or ''
        }
    else:
        profile = {
            'user_id': user_id,
            'name': user_name,
            'email': '',
            'joined_date': None,
            'bio': '',
            'location': '',
            'favorite_food': '',
            'avatar': ''
        }
    
    statistics = {
        'total_recipes': stats[0] if stats else 0,
        'total_likes_received': stats[1] if stats else 0,
        'total_comments': stats[2] if stats else 0,
        'total_saved': stats[3] if stats else 0,
        'total_likes_given': stats[4] if stats else 0
    }
    
    context = {
        'profile': profile,
        'statistics': statistics,
        'page_title': 'My Profile'
    }
    
    # FIXED: Correct render syntax - request first, then template, then context
    return render(request, 'auth/user_profile.html', context)


# ==============================================
# UPDATE PROFILE
# ==============================================
def update_profile(request):
    """
    Update user profile information
    """
    if not request.session.get('user_id'):
        messages.error(request, 'Please login to update your profile')
        return redirect('login')
    
    if request.method == 'POST':
        user_id = request.session['user_id']
        bio = request.POST.get('bio', '')
        location = request.POST.get('location', '')
        favorite_food = request.POST.get('favorite_food', '')
        
        with connection.cursor() as cursor:
            try:
                cursor.callproc('UpdateUserProfile', [user_id, bio, location, favorite_food])
            except:
                cursor.execute("""
                    INSERT INTO user_profiles (user_id, bio, location, favorite_food)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        bio = VALUES(bio),
                        location = VALUES(location),
                        favorite_food = VALUES(favorite_food)
                """, [user_id, bio, location, favorite_food])
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('user_profile')
    
    return redirect('user_profile')


# ==============================================
# DELETE MY RECIPE
# ==============================================
def delete_my_recipe(request, recipe_id):
    """
    Delete a recipe created by the user
    """
    if not request.session.get('user_id'):
        return JsonResponse({'error': 'Not logged in'}, status=401)
    
    user_id = request.session['user_id']
    
    with connection.cursor() as cursor:
        try:
            cursor.callproc('DeleteRecipe', [recipe_id, user_id])
        except:
            cursor.execute("DELETE FROM recipes WHERE recipe_id = %s AND user_id = %s", [recipe_id, user_id])
    
    messages.success(request, 'Recipe deleted successfully!')
    return redirect('my_recipes')


# ==============================================
# REMOVE SAVED RECIPE
# ==============================================
def remove_saved_recipe(request, saved_id):
    """
    Remove a recipe from saved/bookmarked list
    """
    if not request.session.get('user_id'):
        return JsonResponse({'error': 'Not logged in'}, status=401)
    
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM saved_recipes WHERE saved_id = %s", [saved_id])
    
    messages.success(request, 'Recipe removed from saved list!')
    return redirect('saved_recipes')


# ==============================================
# API: DELETE RECIPE (AJAX)
# ==============================================
def delete_recipe_api(request, recipe_id):
    """API endpoint to delete a recipe"""
    if not request.session.get('user_id'):
        return JsonResponse({'error': 'Not logged in'}, status=401)
    
    user_id = request.session['user_id']
    
    with connection.cursor() as cursor:
        try:
            cursor.callproc('DeleteRecipe', [recipe_id, user_id])
        except:
            cursor.execute("DELETE FROM recipes WHERE recipe_id = %s AND user_id = %s", [recipe_id, user_id])
    
    return JsonResponse({'success': True})


# ==============================================
# API: REMOVE SAVED (AJAX)
# ==============================================
def remove_saved_api(request, saved_id):
    """API endpoint to remove a saved recipe"""
    if not request.session.get('user_id'):
        return JsonResponse({'error': 'Not logged in'}, status=401)
    
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM saved_recipes WHERE saved_id = %s", [saved_id])
    
    return JsonResponse({'success': True})
    


# ==============================================
# FAVORITES (LIKED RECIPES) PAGE
# ==============================================
def favorites(request):
    """
    Display all recipes that the logged-in user has liked/favorited
    """
    if not request.session.get('user_id'):
        messages.error(request, 'Please login to view your favorites')
        return redirect('login')
    
    user_id = request.session['user_id']
    favorites_list = []
    
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                l.like_id,
                r.recipe_id,
                r.title,
                r.description,
                r.image,
                u.name as author_name,
                l.created_at as liked_at,
                (SELECT COUNT(*) FROM likes WHERE recipe_id = r.recipe_id) as likes_count,
                (SELECT COUNT(*) FROM comments WHERE recipe_id = r.recipe_id) as comments_count
            FROM likes l
            JOIN recipes r ON l.recipe_id = r.recipe_id
            JOIN users u ON r.user_id = u.user_id
            WHERE l.user_id = %s
            ORDER BY l.created_at DESC
        """, [user_id])
        favorites = cursor.fetchall()
    
    for fav in favorites:
        favorites_list.append({
            'like_id': fav[0],
            'recipe_id': fav[1],
            'title': fav[2],
            'description': fav[3],
            'image': fav[4],
            'author_name': fav[5],
            'liked_at': fav[6],
            'likes_count': fav[7] if len(fav) > 7 else 0,
            'comments_count': fav[8] if len(fav) > 8 else 0
        })
    
    context = {
        'favorites': favorites_list,
        'total_favorites': len(favorites_list),
        'page_title': 'My Favorites'
    }
    
    return render(request, 'auth/favorites.html', context)


# ==============================================
# REMOVE FAVORITE (UNLIKE) API
# ==============================================
def remove_favorite_api(request, recipe_id):
    """API endpoint to remove a recipe from favorites"""
    if not request.session.get('user_id'):
        return JsonResponse({'error': 'Not logged in'}, status=401)
    
    user_id = request.session['user_id']
    
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM likes WHERE recipe_id = %s AND user_id = %s", [recipe_id, user_id])
    
    return JsonResponse({'success': True})


# ==============================================
# MY REVIEWS PAGE
# ==============================================
def my_reviews(request):
    """
    Display all reviews/comments written by the logged-in user
    """
    if not request.session.get('user_id'):
        messages.error(request, 'Please login to view your reviews')
        return redirect('login')
    
    user_id = request.session['user_id']
    reviews_list = []
    
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                c.comment_id,
                c.comment,
                c.rating,
                c.created_at,
                r.recipe_id,
                r.title,
                r.image,
                u.name as recipe_author
            FROM comments c
            JOIN recipes r ON c.recipe_id = r.recipe_id
            JOIN users u ON r.user_id = u.user_id
            WHERE c.user_id = %s
            ORDER BY c.created_at DESC
        """, [user_id])
        reviews = cursor.fetchall()
    
    for review in reviews:
        reviews_list.append({
            'comment_id': review[0],
            'comment': review[1],
            'rating': review[2],
            'created_at': review[3],
            'recipe_id': review[4],
            'recipe_title': review[5],
            'recipe_image': review[6],
            'recipe_author': review[7]
        })
    
    # Calculate average rating of user's reviews
    avg_rating = 0
    if reviews_list:
        total_rating = sum(r['rating'] for r in reviews_list)
        avg_rating = round(total_rating / len(reviews_list), 1)
    
    context = {
        'reviews': reviews_list,
        'total_reviews': len(reviews_list),
        'avg_rating': avg_rating,
        'page_title': 'My Reviews'
    }
    
    return render(request, 'auth/my_reviews.html', context)


# ==============================================
# EDIT REVIEW PAGE
# ==============================================
def edit_review(request, comment_id):
    """
    Edit a specific review/comment
    """
    if not request.session.get('user_id'):
        messages.error(request, 'Please login to edit your review')
        return redirect('login')
    
    user_id = request.session['user_id']
    
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT c.comment_id, c.comment, c.rating, c.recipe_id, r.title
            FROM comments c
            JOIN recipes r ON c.recipe_id = r.recipe_id
            WHERE c.comment_id = %s AND c.user_id = %s
        """, [comment_id, user_id])
        review = cursor.fetchone()
    
    if not review:
        messages.error(request, 'Review not found')
        return redirect('my_reviews')
    
    if request.method == 'POST':
        comment_text = request.POST.get('comment')
        rating = int(request.POST.get('rating', 0))
        
        if not comment_text or rating < 1 or rating > 5:
            messages.error(request, 'Please provide valid comment and rating')
            return render(request, 'auth/edit_review.html', {'review': review})
        
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE comments 
                SET comment = %s, rating = %s, updated_at = NOW()
                WHERE comment_id = %s
            """, [comment_text, rating, comment_id])
        
        messages.success(request, 'Review updated successfully!')
        return redirect('my_reviews')
    
    context = {
        'review': {
            'comment_id': review[0],
            'comment': review[1],
            'rating': review[2],
            'recipe_id': review[3],
            'recipe_title': review[4]
        }
    }
    
    return render(request, 'auth/edit_review.html', context)


# ==============================================
# DELETE REVIEW API
# ==============================================
def delete_review_api(request, comment_id):
    """API endpoint to delete a review"""
    if not request.session.get('user_id'):
        return JsonResponse({'error': 'Not logged in'}, status=401)
    
    user_id = request.session['user_id']
    
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM comments WHERE comment_id = %s AND user_id = %s", [comment_id, user_id])
    
    return JsonResponse({'success': True})


# ==============================================
# SETTINGS PAGE
# ==============================================
def settings_view(request):
    """
    User settings page - manage account, privacy, and preferences
    """
    if not request.session.get('user_id'):
        messages.error(request, 'Please login to access settings')
        return redirect('login')
    
    user_id = request.session['user_id']
    
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT u.user_id, u.name, u.email, u.created_at,
                   COALESCE(p.bio, '') as bio,
                   COALESCE(p.location, '') as location,
                   COALESCE(p.favorite_food, '') as favorite_food,
                   COALESCE(p.email_notifications, 1) as email_notifications,
                   COALESCE(p.newsletter_subscribed, 1) as newsletter_subscribed,
                   COALESCE(p.profile_visibility, 'public') as profile_visibility
            FROM users u
            LEFT JOIN user_profiles p ON u.user_id = p.user_id
            WHERE u.user_id = %s
        """, [user_id])
        user_data = cursor.fetchone()
    
    if user_data:
        user_info = {
            'user_id': user_data[0],
            'name': user_data[1],
            'email': user_data[2],
            'joined_date': user_data[3],
            'bio': user_data[4] or '',
            'location': user_data[5] or '',
            'favorite_food': user_data[6] or '',
            'email_notifications': bool(user_data[7]),
            'newsletter_subscribed': bool(user_data[8]),
            'profile_visibility': user_data[9] or 'public'
        }
    else:
        user_info = {
            'user_id': user_id,
            'name': request.session.get('user_name'),
            'email': '',
            'joined_date': None,
            'bio': '',
            'location': '',
            'favorite_food': '',
            'email_notifications': True,
            'newsletter_subscribed': True,
            'profile_visibility': 'public'
        }
    
    context = {
        'user': user_info,
        'page_title': 'Settings'
    }
    
    return render(request, 'auth/settings.html', context)


# ==============================================
# UPDATE ACCOUNT SETTINGS
# ==============================================
def update_account_settings(request):
    """
    Update account information (name, email, password)
    """
    if not request.session.get('user_id'):
        return JsonResponse({'error': 'Not logged in'}, status=401)
    
    if request.method == 'POST':
        user_id = request.session['user_id']
        name = request.POST.get('name')
        email = request.POST.get('email')
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        with connection.cursor() as cursor:
            cursor.execute("SELECT password FROM users WHERE user_id = %s", [user_id])
            current_hash = cursor.fetchone()
        
        # Verify current password if changing password
        if new_password:
            if not current_password or hash_password(current_password) != current_hash[0]:
                messages.error(request, 'Current password is incorrect')
                return redirect('settings')
            
            if new_password != confirm_password:
                messages.error(request, 'New passwords do not match')
                return redirect('settings')
            
            if len(new_password) < 6:
                messages.error(request, 'Password must be at least 6 characters')
                return redirect('settings')
            
            # Update password
            new_hash = hash_password(new_password)
            with connection.cursor() as cursor:
                cursor.execute("UPDATE users SET password = %s WHERE user_id = %s", [new_hash, user_id])
            
            messages.success(request, 'Password updated successfully!')
        
        # Update name and email
        with connection.cursor() as cursor:
            cursor.execute("UPDATE users SET name = %s, email = %s WHERE user_id = %s", [name, email, user_id])
        
        # Update session
        request.session['user_name'] = name
        
        messages.success(request, 'Account settings updated successfully!')
        return redirect('settings')
    
    return redirect('settings')


# ==============================================
# UPDATE PREFERENCES
# ==============================================
def update_preferences(request):
    """
    Update user preferences (notifications, newsletter, privacy)
    """
    if not request.session.get('user_id'):
        return JsonResponse({'error': 'Not logged in'}, status=401)
    
    if request.method == 'POST':
        user_id = request.session['user_id']
        email_notifications = request.POST.get('email_notifications') == 'on'
        newsletter_subscribed = request.POST.get('newsletter_subscribed') == 'on'
        profile_visibility = request.POST.get('profile_visibility', 'public')
        
        with connection.cursor() as cursor:
            try:
                cursor.execute("""
                    INSERT INTO user_profiles (user_id, email_notifications, newsletter_subscribed, profile_visibility)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        email_notifications = VALUES(email_notifications),
                        newsletter_subscribed = VALUES(newsletter_subscribed),
                        profile_visibility = VALUES(profile_visibility)
                """, [user_id, email_notifications, newsletter_subscribed, profile_visibility])
            except:
                # If columns don't exist, alter table
                try:
                    cursor.execute("ALTER TABLE user_profiles ADD COLUMN email_notifications BOOLEAN DEFAULT 1")
                except:
                    pass
                try:
                    cursor.execute("ALTER TABLE user_profiles ADD COLUMN newsletter_subscribed BOOLEAN DEFAULT 1")
                except:
                    pass
                try:
                    cursor.execute("ALTER TABLE user_profiles ADD COLUMN profile_visibility VARCHAR(20) DEFAULT 'public'")
                except:
                    pass
                
                cursor.execute("""
                    INSERT INTO user_profiles (user_id, email_notifications, newsletter_subscribed, profile_visibility)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        email_notifications = VALUES(email_notifications),
                        newsletter_subscribed = VALUES(newsletter_subscribed),
                        profile_visibility = VALUES(profile_visibility)
                """, [user_id, email_notifications, newsletter_subscribed, profile_visibility])
        
        messages.success(request, 'Preferences updated successfully!')
        return redirect('settings')
    
    return redirect('settings')


# ==============================================
# DELETE ACCOUNT
# ==============================================
def delete_account(request):
    """
    Delete user account and all associated data
    """
    if not request.session.get('user_id'):
        return JsonResponse({'error': 'Not logged in'}, status=401)
    
    if request.method == 'POST':
        user_id = request.session['user_id']
        password = request.POST.get('password')
        
        with connection.cursor() as cursor:
            cursor.execute("SELECT password FROM users WHERE user_id = %s", [user_id])
            current_hash = cursor.fetchone()
        
        if hash_password(password) != current_hash[0]:
            messages.error(request, 'Incorrect password. Account not deleted.')
            return redirect('settings')
        
        # Delete user (cascade will delete recipes, comments, likes, etc.)
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM users WHERE user_id = %s", [user_id])
        
        # Clear session
        request.session.flush()
        
        messages.success(request, 'Your account has been deleted successfully. We\'re sad to see you go!')
        return redirect('login')
    
    return redirect('settings')    

# ==============================================
# API: SAVE RECIPE (Bookmark)
# ==============================================
def api_save_recipe(request):
    """API endpoint to save/unsave a recipe"""
    if not request.session.get('user_id'):
        return JsonResponse({'error': 'Not logged in'}, status=401)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            recipe_id = data.get('recipe_id')
            action = data.get('action')  # 'save' or 'unsave'
            
            user_id = request.session['user_id']
            
            with connection.cursor() as cursor:
                if action == 'save':
                    cursor.execute("""
                        INSERT INTO saved_recipes (user_id, recipe_id, saved_at)
                        VALUES (%s, %s, NOW())
                        ON DUPLICATE KEY UPDATE saved_at = NOW()
                    """, [user_id, recipe_id])
                else:
                    cursor.execute("""
                        DELETE FROM saved_recipes 
                        WHERE user_id = %s AND recipe_id = %s
                    """, [user_id, recipe_id])
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)


# ==============================================
# API: GET SAVED RECIPES
# ==============================================
def api_get_saved_recipes(request):
    """API endpoint to get all saved recipe IDs for the current user"""
    if not request.session.get('user_id'):
        return JsonResponse({'success': True, 'saved_recipes': []})
    
    user_id = request.session['user_id']
    
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT recipe_id FROM saved_recipes 
            WHERE user_id = %s
        """, [user_id])
        saved = cursor.fetchall()
    
    saved_ids = [s[0] for s in saved]
    return JsonResponse({'success': True, 'saved_recipes': saved_ids})


# ==============================================
# API: ADD RATING
# ==============================================
def api_add_rating(request):
    """API endpoint to add/update a recipe rating"""
    if not request.session.get('user_id'):
        return JsonResponse({'error': 'Not logged in'}, status=401)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            recipe_id = data.get('recipe_id')
            rating = data.get('rating')
            
            user_id = request.session['user_id']
            
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO comments (recipe_id, user_id, comment, rating, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                    ON DUPLICATE KEY UPDATE rating = %s, comment = %s
                """, [recipe_id, user_id, f"Rated {rating} stars", rating, rating, f"Rated {rating} stars"])
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)


# ==============================================
# API: GET SAVED RECIPES COUNT
# ==============================================
def api_get_saved_count(request):
    """API endpoint to get the count of saved recipes for the current user"""
    if not request.session.get('user_id'):
        return JsonResponse({'success': True, 'count': 0})
    
    user_id = request.session['user_id']
    
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*) FROM saved_recipes 
            WHERE user_id = %s
        """, [user_id])
        count = cursor.fetchone()[0]
    
    return JsonResponse({'success': True, 'count': count})


# ==============================================
# API: SAVE/UNSAVE RECIPE
# ==============================================
def api_save_recipe(request):
    """API endpoint to save/unsave a recipe"""
    if not request.session.get('user_id'):
        return JsonResponse({'error': 'Not logged in'}, status=401)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            recipe_id = data.get('recipe_id')
            action = data.get('action')  # 'save' or 'unsave'
            
            user_id = request.session['user_id']
            
            with connection.cursor() as cursor:
                if action == 'save':
                    cursor.execute("""
                        INSERT INTO saved_recipes (user_id, recipe_id, saved_at)
                        VALUES (%s, %s, NOW())
                        ON DUPLICATE KEY UPDATE saved_at = NOW()
                    """, [user_id, recipe_id])
                else:
                    cursor.execute("""
                        DELETE FROM saved_recipes 
                        WHERE user_id = %s AND recipe_id = %s
                    """, [user_id, recipe_id])
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)


# ==============================================
# API: TOGGLE LIKE/FAVORITE (No duplicates)
# ==============================================
def api_toggle_like(request):
    """API endpoint to like/unlike a recipe (add to favorites) - prevents duplicates"""
    if not request.session.get('user_id'):
        return JsonResponse({'error': 'Not logged in', 'success': False}, status=401)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            recipe_id = data.get('recipe_id')
            action = data.get('action')  # 'like' or 'unlike'
            
            user_id = request.session['user_id']
            
            with connection.cursor() as cursor:
                if action == 'like':
                    # Check if already exists to prevent duplicate
                    cursor.execute("SELECT * FROM likes WHERE recipe_id = %s AND user_id = %s", [recipe_id, user_id])
                    existing = cursor.fetchone()
                    if existing:
                        return JsonResponse({'success': True, 'error': 'Already exists', 'message': 'Already in favorites'})
                    
                    cursor.execute("""
                        INSERT INTO likes (recipe_id, user_id, created_at)
                        VALUES (%s, %s, NOW())
                    """, [recipe_id, user_id])
                else:
                    cursor.execute("""
                        DELETE FROM likes 
                        WHERE recipe_id = %s AND user_id = %s
                    """, [recipe_id, user_id])
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)


# ==============================================
# API: ADD COMMENT
# ==============================================
def api_add_comment(request):
    """API endpoint to add a comment/review"""
    if not request.session.get('user_id'):
        return JsonResponse({'error': 'Not logged in', 'success': False}, status=401)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            recipe_id = data.get('recipe_id')
            comment = data.get('comment')
            rating = data.get('rating')
            
            user_id = request.session['user_id']
            
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO comments (recipe_id, user_id, comment, rating, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                """, [recipe_id, user_id, comment, rating])
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)


# ==============================================
# API: DELETE COMMENT
# ==============================================
def api_delete_comment(request):
    """API endpoint to delete a comment/review"""
    if not request.session.get('user_id'):
        return JsonResponse({'error': 'Not logged in', 'success': False}, status=401)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            comment_id = data.get('comment_id')
            
            user_id = request.session['user_id']
            
            with connection.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM comments 
                    WHERE comment_id = %s AND user_id = %s
                """, [comment_id, user_id])
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)
    

# ==============================================
# API: TOGGLE COMMENT LIKE
# ==============================================
def api_toggle_comment_like(request):
    """API endpoint to like/unlike a comment"""
    if not request.session.get('user_id'):
        return JsonResponse({'error': 'Not logged in', 'success': False}, status=401)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            comment_id = data.get('comment_id')
            action = data.get('action')
            
            user_id = request.session['user_id']
            
            with connection.cursor() as cursor:
                if action == 'like':
                    cursor.execute("""
                        INSERT INTO comment_likes (comment_id, user_id, created_at)
                        VALUES (%s, %s, NOW())
                        ON DUPLICATE KEY UPDATE created_at = NOW()
                    """, [comment_id, user_id])
                else:
                    cursor.execute("""
                        DELETE FROM comment_likes WHERE comment_id = %s AND user_id = %s
                    """, [comment_id, user_id])
                
                # Get updated like count
                cursor.execute("SELECT COUNT(*) FROM comment_likes WHERE comment_id = %s", [comment_id])
                likes_count = cursor.fetchone()[0]
            
            return JsonResponse({'success': True, 'likes_count': likes_count})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)


# ==============================================
# API: ADD REPLY
# ==============================================
def api_add_reply(request):
    """API endpoint to add a reply to a comment"""
    if not request.session.get('user_id'):
        return JsonResponse({'error': 'Not logged in', 'success': False}, status=401)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            comment_id = data.get('comment_id')
            reply_text = data.get('reply_text')
            recipe_id = data.get('recipe_id')
            
            user_id = request.session['user_id']
            
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO comment_replies (comment_id, user_id, reply_text, recipe_id, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                """, [comment_id, user_id, reply_text, recipe_id])
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)


# ==============================================
# API: GET REPLIES
# ==============================================
def api_get_replies(request, comment_id):
    """API endpoint to get all replies for a comment"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT cr.reply_id, cr.reply_text, cr.created_at, u.name as author_name,
                   (SELECT COUNT(*) FROM reply_likes WHERE reply_id = cr.reply_id) as likes_count
            FROM comment_replies cr
            JOIN users u ON cr.user_id = u.user_id
            WHERE cr.comment_id = %s
            ORDER BY cr.created_at ASC
        """, [comment_id])
        replies = cursor.fetchall()
    
    reply_list = []
    user_id = request.session.get('user_id')
    
    for reply in replies:
        reply_list.append({
            'reply_id': reply[0],
            'reply_text': reply[1],
            'created_at': reply[2].strftime('%Y-%m-%d %H:%M:%S') if reply[2] else None,
            'author_name': reply[3],
            'likes_count': reply[4],
            'can_delete': user_id and reply[3] == request.session.get('user_name')
        })
    
    return JsonResponse({'success': True, 'replies': reply_list})


# ==============================================
# API: TOGGLE REPLY LIKE
# ==============================================
def api_toggle_reply_like(request):
    """API endpoint to like/unlike a reply"""
    if not request.session.get('user_id'):
        return JsonResponse({'error': 'Not logged in', 'success': False}, status=401)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            reply_id = data.get('reply_id')
            action = data.get('action')
            
            user_id = request.session['user_id']
            
            with connection.cursor() as cursor:
                if action == 'like':
                    cursor.execute("""
                        INSERT INTO reply_likes (reply_id, user_id, created_at)
                        VALUES (%s, %s, NOW())
                        ON DUPLICATE KEY UPDATE created_at = NOW()
                    """, [reply_id, user_id])
                else:
                    cursor.execute("""
                        DELETE FROM reply_likes WHERE reply_id = %s AND user_id = %s
                    """, [reply_id, user_id])
                
                cursor.execute("SELECT COUNT(*) FROM reply_likes WHERE reply_id = %s", [reply_id])
                likes_count = cursor.fetchone()[0]
            
            return JsonResponse({'success': True, 'likes_count': likes_count})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)


# ==============================================
# API: DELETE REPLY
# ==============================================
def api_delete_reply(request):
    """API endpoint to delete a reply"""
    if not request.session.get('user_id'):
        return JsonResponse({'error': 'Not logged in', 'success': False}, status=401)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            reply_id = data.get('reply_id')
            
            user_id = request.session['user_id']
            
            with connection.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM comment_replies 
                    WHERE reply_id = %s AND user_id = %s
                """, [reply_id, user_id])
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)    