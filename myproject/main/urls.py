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

    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),
    path('student/analytics/', views.student_analytics, name='student_analytics'),

    path('teacher/dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/analytics/', views.teacher_analytics, name='teacher_analytics'),

    path('export-data/', views.export_data_page, name='export_data_page'),
    path('export/courses.csv', views.export_courses_csv, name='export_courses_csv'),
    path('export/enrollments.csv', views.export_enrollments_csv, name='export_enrollments_csv'),
    path('export/learning-records.csv', views.export_learning_records_csv, name='export_learning_records_csv'),
    path('export/profiles.csv', views.export_profiles_csv, name='export_profiles_csv'),

    path('export/orders.csv', views.export_orders_csv, name='export_orders_csv'),
    path('export/order-items.csv', views.export_order_items_csv, name='export_order_items_csv'),
    path('export/payments.csv', views.export_payments_csv, name='export_payments_csv'),
    path('export/coupon-usage.csv', views.export_coupon_usage_csv, name='export_coupon_usage_csv'),
    path('export/reviews.csv', views.export_reviews_csv, name='export_reviews_csv'),
    path('export/course-lessons.csv', views.export_course_lessons_csv, name='export_course_lessons_csv'),

    path('register/', views.register, name='register'),
    path('register-success/', views.register_success, name='register_success'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('profile/', views.profile_view, name='profile'),
    path('my-courses/', views.my_courses, name='my_courses'),

    path('create-course/', views.create_course, name='create_course'),

    # 購物車
    path('cart/', views.view_cart, name='view_cart'),
    path('cart/add/<int:course_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/checkout/', views.cart_checkout, name='cart_checkout'),

    # 收藏
    path('favorites/', views.my_favorites, name='my_favorites'),
    path('favorites/toggle/<int:course_id>/', views.toggle_favorite, name='toggle_favorite'),

    # 退款
    path('refunds/', views.my_refunds, name='my_refunds'),
    path('refunds/request/<int:order_id>/', views.request_refund, name='request_refund'),

    # 優惠券領取
    path('coupons/', views.coupon_list, name='coupon_list'),
    path('coupons/claim/<int:coupon_id>/', views.claim_coupon, name='claim_coupon'),
    path('my-coupons/', views.my_coupons, name='my_coupons'),

    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='main/password_reset.html'
    ), name='password_reset'),

    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='main/password_reset_done.html'
    ), name='password_reset_done'),
]