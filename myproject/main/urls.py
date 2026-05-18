from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.home, name='home'),

    path('course/<int:course_id>/', views.course_detail, name='course_detail'),
    path('course/<int:course_id>/buy/', views.buy_course, name='buy_course'),
    path('course/<int:course_id>/checkout/', views.checkout, name='checkout'),
    path('order/<int:order_id>/success/', views.order_success, name='order_success'),
    path('course/<int:course_id>/purchase-success/', views.purchase_success, name='purchase_success'),
    path('course/<int:course_id>/watch/', views.watch_course, name='watch_course'),
    path('course/<int:course_id>/edit/', views.edit_course, name='edit_course'),
    path('course/<int:course_id>/delete/', views.delete_course, name='delete_course'),

    path('export-data/', views.export_data_page, name='export_data_page'),
    path('export/courses.csv', views.export_courses_csv, name='export_courses_csv'),
    path('export/enrollments.csv', views.export_enrollments_csv, name='export_enrollments_csv'),
    path('export/learning-records.csv', views.export_learning_records_csv, name='export_learning_records_csv'),
    path('export/profiles.csv', views.export_profiles_csv, name='export_profiles_csv'),

    path('register/', views.register, name='register'),
    path('register-success/', views.register_success, name='register_success'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('profile/', views.profile_view, name='profile'),
    path('my-courses/', views.my_courses, name='my_courses'),

    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),
    path('teacher/dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('create-course/', views.create_course, name='create_course'),

    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='main/password_reset.html'
    ), name='password_reset'),

    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='main/password_reset_done.html'
    ), name='password_reset_done'),
]