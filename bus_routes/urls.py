#from AppData.Local.Programs.Python.Python313.Lib.test.test_importlib.resources.test_resource import names
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('search/', views.search_route, name='search_route'),
    path('api/bus_stops/', views.get_bus_stops_json, name='api_bus_stops'),
    path('between-stops/', views.search_route, name='between_stops'),

    # Authentication URLs
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Saved routes URLs
    path('save-route/', views.save_route, name='save_route'),
    path('view-route/<int:route_id>/', views.view_saved_route, name='view_saved_route'),
    path('delete-route/<int:route_id>/', views.delete_saved_route, name='delete_saved_route'),
    
    # Admin Dashboard URLs
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-dashboard/bus-stops/', views.admin_bus_stops, name='admin_bus_stops'),
    path('admin-dashboard/bus-stops/add/', views.admin_bus_stop_add, name='admin_bus_stop_add'),
    path('admin-dashboard/bus-stops/edit/<int:stop_id>/', views.admin_bus_stop_edit, name='admin_bus_stop_edit'),
    path('admin-dashboard/bus-stops/delete/<int:stop_id>/', views.admin_bus_stop_delete, name='admin_bus_stop_delete'),
    path('admin-dashboard/bus-lines/', views.admin_bus_lines, name='admin_bus_lines'),
    path('admin-dashboard/route-segments/', views.admin_route_segments, name='admin_route_segments'),
    path('admin-dashboard/users/', views.admin_users, name='admin_users'),
    path('admin-dashboard/saved-routes/', views.admin_saved_routes, name='admin_saved_routes'),
    path('admin-dashboard/saved-routes/edit/<int:route_id>/', views.admin_saved_route_edit, name='admin_saved_route_edit'),
    path('admin-dashboard/saved-routes/delete/<int:route_id>/', views.admin_saved_route_delete, name='admin_saved_route_delete'),
    path('admin-dashboard/route-segments/', views.admin_route_segments, name='admin_route_segments'),
    path('admin-dashboard/route-segments/add/', views.admin_route_segment_add, name='admin_route_segment_add'),
    path('admin-dashboard/route-segments/edit/<int:segment_id>/', views.admin_route_segment_edit, name='admin_route_segment_edit'),
    path('admin-dashboard/route-segments/delete/<int:segment_id>/', views.admin_route_segment_delete, name='admin_route_segment_delete'),
    # Add other admin URLs if you have them, e.g., for users or saved routes
    path('admin-dashboard/saved-routes/', views.admin_saved_routes, name='admin_saved_routes'),
    path('admin-dashboard/users/', views.admin_users, name='admin_users'),
    path('all_bus_lines/', views.all_bus_lines, name='all_bus_lines'),
    path('rangoon_map/', views.rangoon_map, name='rangoon_map'),
    path('complaint_numbers/', views.complaint_numbers, name='complaint_numbers'),
    path('complaints/', views.complaints_view, name='admin_complaints'),
    path('submit_complaint/', views.submit_complaint_view, name='submit_complaint'),
    path('api/bus_lines/', views.bus_lines_api, name='bus_lines_api'),
    path('api/bus_lines/<int:bus_line_id>/route/', views.bus_line_route_api, name='bus_line_route_api'),
    path('api/bus_stops/', views.get_bus_stops_json, name='bus_stops_json'),
    path('admin-dashboard/bus-lines/', views.admin_bus_lines, name='admin_bus_lines'),
    path('admin-dashboard/bus-lines/add/', views.admin_bus_line_add, name='admin_bus_line_add'),
    path('admin-dashboard/bus-lines/edit/<int:line_id>/', views.admin_bus_line_edit, name='admin_bus_line_edit'),
    path('admin-dashboard/bus-lines/delete/<int:line_id>/', views.admin_bus_line_delete, name='admin_bus_line_delete'),
    path('admin-dashboard/users/', views.admin_users, name='admin_users'),
    path('admin-dashboard/users/edit/<int:user_id>/', views.admin_user_edit, name='admin_user_edit'),
    path('admin-dashboard/users/delete/<int:user_id>/', views.admin_user_delete, name='admin_user_delete'),
    path('api/complaint_numbers/<str:line_number>/', views.get_complaint_numbers_api, name='api_complaint_numbers'),
    
    # User location tracking API endpoints

]
