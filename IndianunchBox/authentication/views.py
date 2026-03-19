from django.shortcuts import render, redirect
from django.core.files.storage import FileSystemStorage
from django.db import connection
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
import hashlib
# HASH PASSWORD
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

from django.shortcuts import render

from django.db import connection

def home(request):
    if not request.session.get('user_id'):
        return redirect('login')

    # Fetch all recipes (latest first)
    with connection.cursor() as cursor:
        cursor.execute("SELECT recipe_id, title, description, image FROM recipes ORDER BY recipe_id DESC")
        recipes = cursor.fetchall()  # List of tuples

    return render(request, 'home.html', {'recipes': recipes})

# REGISTER
def register_view(request):
    if request.method == "POST":
        name = request.POST['name']
        email = request.POST['email']
        password = hash_password(request.POST['password'])

        with connection.cursor() as cursor:
            cursor.callproc('RegisterUser', [name, email, password])

        return redirect('login')

    return render(request, 'auth/register.html')


# LOGIN
def login_view(request):
    if request.method == "POST":
        email = request.POST['email']
        password = hash_password(request.POST['password'])

        with connection.cursor() as cursor:
            cursor.callproc('LoginUser', [email])
            user = cursor.fetchone()

        if user and user[3] == password:
            request.session['user_id'] = user[0]
            request.session['user_name'] = user[1]
            return redirect('home')

    return render(request, 'auth/login.html')
    

def logout_view(request):
    request.session.flush()
    return redirect('login')    


from django.core.files.storage import FileSystemStorage

# ADD RECIPE
from django.shortcuts import render, redirect
from django.core.files.storage import FileSystemStorage
from django.db import connection
import hashlib

# Hash password (already exists)
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Add Recipe
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


# View Recipes Page (feed)
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


# Recipe Detail + comments
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
    if request.method == "POST":
        comment_text = request.POST['comment']
        rating = int(request.POST['rating'])
        with connection.cursor() as cursor:
            cursor.callproc('AddComment', [id, request.session['user_id'], comment_text, rating])
        return redirect(f'/recipe/{id}/')

    return render(request, 'recipes/recipe_detail.html', {
        'recipe': recipe,
        'comments': comments
    })
    
    
    
from django.shortcuts import render
from django.db import connection
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
import os
from django.conf import settings  # Needed for absolute media path

def download_recipe_pdf(request, id):
    # Fetch recipe from DB
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT r.title, r.description, r.ingredients, r.steps, r.image, u.name
            FROM recipes r
            JOIN users u ON r.user_id = u.user_id
            WHERE r.recipe_id=%s
        """, [id])
        recipe = cursor.fetchone()

    if not recipe:
        return HttpResponse("Recipe not found")

    # Full image path for xhtml2pdf
    image_path = os.path.join(settings.BASE_DIR, 'media', recipe[4])

    # Render template
    template_path = 'recipes/recipe_pdf.html'
    context = {
        'recipe': recipe,
        'image_path': image_path
    }
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{recipe[0]}.pdf"'

    template = get_template(template_path)
    html = template.render(context)

    # Generate PDF
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Error generating PDF')
    return response



from django.http import JsonResponse

def toggle_like(request, recipe_id):
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'error':'Not logged in'})

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