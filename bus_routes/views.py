import heapq
import json
import requests
from collections import defaultdict
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core import serializers
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse

from .forms import CustomUserCreationForm, CustomAuthenticationForm, SavedRouteForm
from .models import BusStop, BusLine, RouteSegment, UserProfile, SavedRoute, RouteSearch, Complaint

OSRM_BASE_URL = "http://router.project-osrm.org/route/v1/driving/"


def get_route_details_from_osrm(coords_list):
    if not coords_list or len(coords_list) < 2:
        return None, None

    valid_coords = [(lat, lon) for lat, lon in coords_list if lat is not None and lon is not None]

    if len(valid_coords) < 2:
        return None, None

    coordinates_str = ";".join([f"{lon},{lat}" for lat, lon in valid_coords])
    url = f"{OSRM_BASE_URL}{coordinates_str}?overview=false"

    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()

        if data and data['code'] == 'Ok' and data['routes']:
            route = data['routes'][0]
            distance_meters = route['distance']
            duration_seconds = route['duration']

            distance_km = distance_meters / 1000
            duration_minutes = duration_seconds / 60
            return distance_km, duration_minutes
        else:
            print(f"OSRM API error or no route found: {data.get('code', 'Unknown error')}")
            return None, None
    except requests.exceptions.RequestException as e:
        print(f"Error calling OSRM API: {e}")
        return None, None
    except Exception as e:
        print(f"An unexpected error occurred while processing OSRM response: {e}")
        return None, None


def home(request):
    bus_stops = BusStop.objects.all().order_by('name_en', 'road_name_en')
    saved_routes = None
    if request.user.is_authenticated:
        saved_routes = SavedRoute.objects.filter(user=request.user).order_by('-created_at')

    return render(request, 'home.html', {
        'bus_stops': bus_stops,
        'saved_routes': saved_routes
    })


def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            email = form.cleaned_data.get('email')
            password = form.cleaned_data.get('password2')

            # Check if password has at least 8 characters and contains at least one digit
            if len(password) < 8 or not any(char.isdigit() for char in password):
                messages.error(request, 'Password must be at least 8 characters long and contain at least one digit.')
                return render(request, 'auth/register.html', {'form': form})

            # Check if a user with this username already exists
            if User.objects.filter(username=username).exists():
                messages.error(request, 'This username is already taken. Please choose another one.')
                return render(request, 'auth/register.html', {'form': form})

            # Check if a user with this email already exists
            if User.objects.filter(email=email).exists():
                messages.error(request, 'This email is already registered. Please use a different one.')
                return render(request, 'auth/register.html', {'form': form})

            user = User.objects.create_user(username=username, email=email, password=password)
            user.save()

            login(request, user)
            messages.success(request, 'Registration successful!')
            return redirect('home')
    else:
        form = CustomUserCreationForm()

    return render(request, 'auth/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {username}!')
                next_page = request.GET.get('next', 'home')
                return redirect(next_page)
            else:
                messages.error(request, 'Invalid username or password.')
    else:
        form = CustomAuthenticationForm()

    return render(request, 'auth/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('home')


@login_required
def save_route(request):
    if request.method == 'POST':
        form = SavedRouteForm(request.POST)
        if form.is_valid():
            saved_route = form.save(commit=False)
            saved_route.user = request.user
            saved_route.save()
            messages.success(request, 'Route saved successfully!')
            return redirect('home')
    else:
        start_stop_id = request.GET.get('start_stop_id')
        end_stop_id = request.GET.get('end_stop_id')
        bus_line_number = request.GET.get('bus_line_number')

        initial_data = {}
        if start_stop_id:
            try:
                initial_data['start_stop'] = BusStop.objects.get(id=start_stop_id)
            except BusStop.DoesNotExist:
                pass

        if end_stop_id:
            try:
                initial_data['end_stop'] = BusStop.objects.get(id=end_stop_id)
            except BusStop.DoesNotExist:
                pass

        if bus_line_number:
            initial_data['line_number'] = bus_line_number

        form = SavedRouteForm(initial=initial_data)

    return render(request, 'save_route.html', {'form': form})


@login_required
def delete_saved_route(request, route_id):
    route = get_object_or_404(SavedRoute, id=route_id, user=request.user)
    route.delete()
    messages.success(request, 'Route deleted successfully!')
    return redirect('home')


@login_required
def saved_route_api(request, route_id):
    try:
        saved_route = SavedRoute.objects.get(id=route_id, user=request.user)
        data = {
            'id': saved_route.id,
            'name': saved_route.name,
            'start_stop_name_en': saved_route.start_stop.name_en,
            'start_stop_name_mm': saved_route.start_stop.name_mm,
            'end_stop_name_en': saved_route.end_stop.name_en,
            'end_stop_name_mm': saved_route.end_stop.name_mm,
        }
        return JsonResponse(data)
    except SavedRoute.DoesNotExist:
        return JsonResponse({'error': 'Route not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def view_saved_route(request, route_id):
    # Get the saved route or return 404 if not found
    saved_route = get_object_or_404(SavedRoute, id=route_id, user=request.user)
    
    # Get the start and end stops from the saved route
    start_stop = saved_route.start_stop
    end_stop = saved_route.end_stop
    
    # Find direct bus lines between these stops
    direct_bus_lines = BusLine.objects.filter(
        route_segments__bus_stop=start_stop
    ).filter(
        route_segments__bus_stop=end_stop
    ).distinct().order_by('line_number')
    
    # Find the shortest path between these stops
    shortest_path = find_shortest_path(start_stop.id, end_stop.id)
    
    # Prepare the results for display
    results = []
    
    # Add direct bus lines to results if any
    if direct_bus_lines.exists():
        direct_lines_result = {
            'type': 'direct',
            'bus_lines': list(direct_bus_lines),
            'start_stop': start_stop,
            'end_stop': end_stop
        }
        results.append(direct_lines_result)
    
    # Add shortest path to results if found
    if shortest_path:
        results.append({
            'type': 'shortest_path',
            'path': shortest_path,
            'start_stop': start_stop,
            'end_stop': end_stop
        })
    
    # Use the view_saved_route.html template
    return render(request, 'view_saved_route.html', {
        'saved_route': saved_route,
        'results': results,
        'start_stop': start_stop,
        'end_stop': end_stop,
        'error_message': None if results else "No routes found between these stops."
    })


def parse_stop_name_with_road(full_name):
    if '(' in full_name and full_name.endswith(')'):
        parts = full_name.rsplit('(', 1)
        stop_name = parts[0].strip()
        road_name = parts[1][:-1].strip()
        return stop_name, road_name
    return full_name, None


def get_bus_stop_object(stop_name_raw):
    stop_name, road_name = parse_stop_name_with_road(stop_name_raw)

    query = Q(name_en__iexact=stop_name) | Q(name_mm__iexact=stop_name)
    if road_name:
        query = (Q(name_en__iexact=stop_name, road_name_en__iexact=road_name) |
                 Q(name_mm__iexact=stop_name, road_name_mm__iexact=road_name))
        if not BusStop.objects.filter(query).exists():
            query = Q(name_en__iexact=stop_name) | Q(name_mm__iexact=stop_name)
    else:
        no_road_query = (
                Q(name_en__iexact=stop_name, road_name_en__isnull=True) |
                Q(name_en__iexact=stop_name, road_name_en__iexact='') |
                Q(name_mm__iexact=stop_name, road_name_mm__isnull=True) |
                Q(name_mm__iexact=stop_name, road_name_mm__iexact='')
        )
        if BusStop.objects.filter(no_road_query).exists():
            query = no_road_query
        else:
            query = Q(name_en__iexact=stop_name) | Q(name_mm__iexact=stop_name)

    return BusStop.objects.filter(query).first()


def find_shortest_path(start_stop_id, end_stop_id):
    if start_stop_id == end_stop_id:
        return []

    graph = defaultdict(list)
    all_stops = list(BusStop.objects.all())

    all_route_segments = list(RouteSegment.objects.all().select_related('bus_stop', 'bus_line'))
    segments_by_line = defaultdict(list)
    for segment in all_route_segments:
        segments_by_line[segment.bus_line_id].append(segment)

    for bus_line_id, segments in segments_by_line.items():
        segments.sort(key=lambda s: s.order)
        for i in range(len(segments) - 1):
            stop_a = segments[i].bus_stop
            stop_b = segments[i + 1].bus_stop
            bus_line_number = segments[i].bus_line.line_number
            graph[stop_a.id].append({'stop_id': stop_b.id, 'line_id': bus_line_id, 'line_number': bus_line_number})
            graph[stop_b.id].append({'stop_id': stop_a.id, 'line_id': bus_line_id, 'line_number': bus_line_number})

    distances = {stop.id: float('inf') for stop in all_stops}
    predecessors = {stop.id: None for stop in all_stops}
    distances[start_stop_id] = 0
    priority_queue = [(0, start_stop_id, None)]

    shortest_path_found = False

    while priority_queue:
        cost, current_stop_id, current_line_id = heapq.heappop(priority_queue)

        if cost > distances[current_stop_id]:
            continue

        if current_stop_id == end_stop_id:
            shortest_path_found = True
            break

        for neighbor in graph[current_stop_id]:
            neighbor_stop_id = neighbor['stop_id']
            neighbor_line_id = neighbor['line_id']

            transfer_cost = 1 if current_line_id is not None and current_line_id != neighbor_line_id else 0
            new_cost = cost + transfer_cost

            if new_cost < distances[neighbor_stop_id]:
                distances[neighbor_stop_id] = new_cost
                predecessors[neighbor_stop_id] = (current_stop_id, neighbor_line_id)
                heapq.heappush(priority_queue, (new_cost, neighbor_stop_id, neighbor_line_id))

    if not shortest_path_found:
        return []

    path = []
    current_stop_id = end_stop_id
    while current_stop_id != start_stop_id:
        prev_stop_id, prev_line_id = predecessors.get(current_stop_id, (None, None))
        if prev_stop_id is None:
            return []

        bus_line = BusLine.objects.filter(id=prev_line_id).first()
        bus_line_number = bus_line.line_number if bus_line else None

        if not path or path[-1]['line_id'] != prev_line_id:
            path.append({
                'start_stop_id': prev_stop_id,
                'end_stop_id': current_stop_id,
                'line_id': prev_line_id,
                'line_number': bus_line_number
            })
        else:
            path[-1]['start_stop_id'] = prev_stop_id
        current_stop_id = prev_stop_id

    path.reverse()
    return path


def get_segment_details(bus_line, start_stop, end_stop):
    start_segment = RouteSegment.objects.filter(bus_line=bus_line, bus_stop=start_stop).first()
    end_segment = RouteSegment.objects.filter(bus_line=bus_line, bus_stop=end_stop).first()

    if not start_segment or not end_segment:
        return None

    if start_segment.order <= end_segment.order:
        segments = RouteSegment.objects.filter(
            bus_line=bus_line,
            order__gte=start_segment.order,
            order__lte=end_segment.order
        ).order_by('order').select_related('bus_stop')
    else:
        segments = RouteSegment.objects.filter(
            bus_line=bus_line,
            order__lte=start_segment.order,
            order__gte=end_segment.order
        ).order_by('-order').select_related('bus_stop')

    if not segments:
        return None

    route_stops_coords = []
    route_stops_display = []
    for segment in segments:
        lat = float(segment.bus_stop.latitude) if segment.bus_stop.latitude else None
        lng = float(segment.bus_stop.longitude) if segment.bus_stop.longitude else None

        if lat is not None and lng is not None:
            route_stops_coords.append((lat, lng))

        route_stops_display.append({
            'name_mm': segment.bus_stop.name_mm,
            'name_en': segment.bus_stop.name_en,
            'road_name_mm': segment.bus_stop.road_name_mm,
            'road_name_en': segment.bus_stop.road_name_en,
            'order': segment.order,
            'latitude': lat,
            'longitude': lng,
            'id': segment.bus_stop.id
        })

    total_distance, total_time = get_route_details_from_osrm(route_stops_coords)

    return {
        'stops_count': segments.count(),
        'total_distance_km': round(total_distance, 2) if total_distance is not None else 'N/A',
        'total_time_minutes': round(total_time, 0) if total_time is not None else 'N/A',
        'route_stops': route_stops_display,
        'start_stop_name': start_stop.name_en,
        'end_stop_name': end_stop.name_en,
    }


def find_stops_between(start_stop, end_stop):
    """
    Find all bus lines that connect start_stop and end_stop,
    and return all stops between them (inclusive) for each line.
    """
    results = []
    
    # Find bus lines that serve both stops
    common_bus_lines = BusLine.objects.filter(
        route_segments__bus_stop=start_stop
    ).filter(
        route_segments__bus_stop=end_stop
    ).distinct()
    
    for bus_line in common_bus_lines:
        # Get all route segments for this bus line, ordered by 'order' field
        route_segments = RouteSegment.objects.filter(
            bus_line=bus_line
        ).order_by('order').select_related('bus_stop')
        
        # Find the positions of start and end stops
        start_position = None
        end_position = None
        
        for i, segment in enumerate(route_segments):
            if segment.bus_stop == start_stop:
                start_position = i
            if segment.bus_stop == end_stop:
                end_position = i
        
        # If both stops found, get all stops between them
        if start_position is not None and end_position is not None:
            # Ensure start comes before end (handle both directions)
            if start_position > end_position:
                start_position, end_position = end_position, start_position
            
            # Get all stops between (inclusive)
            between_segments = route_segments[start_position:end_position + 1]
            
            results.append({
                'bus_line': bus_line,
                'stops': [segment.bus_stop for segment in between_segments],
                'total_stops': len(between_segments),
                'orders': [segment.order for segment in between_segments]
            })
    
    return results


@login_required
def search_route(request):
    start_stop_name_raw = request.GET.get('start_stop', '').strip()
    end_stop_name_raw = request.GET.get('end_stop', '').strip()
    search_type = request.GET.get('search_type', 'bus_stop')
    bus_line_number = request.GET.get('bus_line_number', '').strip()
    single_bus_stop_name_raw = request.GET.get('single_bus_stop', '').strip()

    start_stop_id_param = request.GET.get('start_stop_id')
    end_stop_id_param = request.GET.get('end_stop_id')

    results = []
    error_message = None
    start_stop_obj = None
    end_stop_obj = None
    search_count = None

    # Handle 'between_stops' search type
    if search_type == 'between_stops':
        if not start_stop_name_raw or not end_stop_name_raw:
            error_message = "Please provide both start and end stop names."
            return render(request, 'between_stops_results.html', {
                'between_stops_results': [],
                'start_stop': None,
                'end_stop': None,
                'error_message': error_message
            })
        
        try:
            # Parse the stop names to handle road names in parentheses
            start_stop_obj = get_bus_stop_object(start_stop_name_raw)
            end_stop_obj = get_bus_stop_object(end_stop_name_raw)
            
            if not start_stop_obj:
                error_message = f"Start stop '{start_stop_name_raw}' not found."
            elif not end_stop_obj:
                error_message = f"End stop '{end_stop_name_raw}' not found."
            else:
                # Find all stops between these two stops
                between_stops_results = find_stops_between(start_stop_obj, end_stop_obj)
                
                return render(request, 'between_stops_results.html', {
                    'between_stops_results': between_stops_results,
                    'start_stop': start_stop_obj,
                    'end_stop': end_stop_obj,
                    'error_message': None if between_stops_results else "No bus lines found that connect these stops."
                })
        except Exception as e:
            error_message = f"An error occurred: {str(e)}"
            return render(request, 'between_stops_results.html', {
                'between_stops_results': [],
                'start_stop': None,
                'end_stop': None,
                'error_message': error_message
            })

    # Handle regular bus stop search
    if search_type == 'bus_stop':
        if not start_stop_name_raw or not end_stop_name_raw:
            error_message = "Please enter both start and end bus stops."
        else:
            try:
                start_stop_obj = get_bus_stop_object(start_stop_name_raw)
                end_stop_obj = get_bus_stop_object(end_stop_name_raw)

                if not start_stop_obj or not end_stop_obj:
                    error_message = "Invalid bus stop name(s) entered. Please check and try again."
                else:
                    if request.user.is_authenticated:
                        RouteSearch.objects.create(start_stop=start_stop_obj, end_stop=end_stop_obj, user=request.user)
                    else:
                        RouteSearch.objects.create(start_stop=start_stop_obj, end_stop=end_stop_obj)

                    search_count = RouteSearch.objects.filter(
                        start_stop=start_stop_obj,
                        end_stop=end_stop_obj
                    ).count()

                    direct_bus_lines = BusLine.objects.filter(
                        route_segments__bus_stop=start_stop_obj
                    ).filter(
                        route_segments__bus_stop=end_stop_obj
                    ).distinct().order_by('line_number')

                    if direct_bus_lines.exists():
                        for bus_line in direct_bus_lines:
                            results.append({
                                'bus_line_number': bus_line.line_number,
                                'route_type': 'available_bus_line',
                                'start_stop_name': start_stop_obj.name_en,
                                'end_stop_name': end_stop_obj.name_en,
                                'start_stop_id': start_stop_obj.id,
                                'end_stop_id': end_stop_obj.id,
                            })
                    else:
                        transfer_path = find_shortest_path(start_stop_obj.id, end_stop_obj.id)
                        if transfer_path:
                            total_distance = 0
                            total_time = 0
                            num_transfers = len(transfer_path) - 1

                            transfer_details = []
                            for segment_info in transfer_path:
                                try:
                                    bus_line = BusLine.objects.get(id=segment_info['line_id'])
                                    segment_start_stop = BusStop.objects.get(id=segment_info['start_stop_id'])
                                    segment_end_stop = BusStop.objects.get(id=segment_info['end_stop_id'])

                                    segment_data = get_segment_details(bus_line, segment_start_stop, segment_end_stop)

                                    if segment_data:
                                        segment_data['bus_line_number'] = bus_line.line_number
                                        segment_data['start_stop'] = segment_start_stop.name_en
                                        segment_data['end_stop'] = segment_end_stop.name_en
                                        segment_data['distance_km'] = segment_data.get('total_distance_km', 'N/A')
                                        segment_data['time_minutes'] = segment_data.get('total_time_minutes', 'N/A')
                                        segment_data['stops_on_this_segment'] = segment_data.get('route_stops', [])
                                        transfer_details.append(segment_data)

                                        if isinstance(segment_data['distance_km'], (float, int)):
                                            total_distance += segment_data['distance_km']
                                        if isinstance(segment_data['time_minutes'], (float, int)):
                                            total_time += segment_data['time_minutes']
                                except (BusLine.DoesNotExist, BusStop.DoesNotExist) as e:
                                    print(f"Error fetching segment details for transfer route: {e}")
                                    continue

                            if transfer_details:
                                results.append({
                                    'route_type': 'transfer',
                                    'transfer_details': transfer_details,
                                    'total_distance_km': round(total_distance, 2) if total_distance > 0 else 'N/A',
                                    'total_time_minutes': round(total_time, 0) if total_time > 0 else 'N/A',
                                    'num_transfers': num_transfers,
                                })
                            else:
                                error_message = "No valid transfer route could be constructed."
                        else:
                            error_message = f"No direct or transfer route found between {start_stop_obj.name_en} and {end_stop_obj.name_en}."
            except Exception as e:
                error_message = f"An error occurred during search: {e}"

    elif search_type == 'detailed_bus_line':
        if not bus_line_number:
            error_message = "Please enter a bus line number."
        else:
            try:
                bus_line = BusLine.objects.get(line_number=bus_line_number)
                if start_stop_id_param and end_stop_id_param:
                    start_stop_obj = get_object_or_404(BusStop, id=start_stop_id_param)
                    end_stop_obj = get_object_or_404(BusStop, id=end_stop_id_param)
                    segment_data = get_segment_details(bus_line, start_stop_obj, end_stop_obj)
                    if segment_data:
                        segment_data.update({
                            'bus_line_number': bus_line.line_number,
                            'route_type': 'segment_line',
                            'start_stop_id': start_stop_obj.id,
                            'end_stop_id': end_stop_obj.id,
                        })
                        results.append(segment_data)
                    else:
                        error_message = f"Could not find segment for Bus {bus_line_number} between specified stops."
                else:
                    all_segments = RouteSegment.objects.filter(bus_line=bus_line).order_by('order').select_related(
                        'bus_stop')
                    if all_segments.exists():
                        start_stop_obj = all_segments.first().bus_stop
                        end_stop_obj = all_segments.last().bus_stop
                        segment_data = get_segment_details(bus_line, start_stop_obj, end_stop_obj)
                        if segment_data:
                            segment_data.update({
                                'bus_line_number': bus_line.line_number,
                                'route_type': 'full_line',
                                'start_stop_id': start_stop_obj.id,
                                'end_stop_id': end_stop_obj.id,
                            })
                            results.append(segment_data)
                    else:
                        error_message = f"No segments found for bus line {bus_line_number}."
            except BusLine.DoesNotExist:
                error_message = "Invalid bus line number entered."
            except Exception as e:
                error_message = f"An error occurred during search: {e}"

    elif search_type == 'bus_line':
        if not bus_line_number:
            error_message = "Please enter a bus line number."
        else:
            try:
                bus_line = BusLine.objects.get(line_number=bus_line_number)
                all_segments = RouteSegment.objects.filter(bus_line=bus_line).order_by('order').select_related(
                    'bus_stop')
                if all_segments.exists():
                    start_stop_obj = all_segments.first().bus_stop
                    end_stop_obj = all_segments.last().bus_stop
                    segment_data = get_segment_details(bus_line, start_stop_obj, end_stop_obj)
                    if segment_data:
                        segment_data.update({
                            'bus_line_number': bus_line.line_number,
                            'route_type': 'full_line',
                            'start_stop_id': start_stop_obj.id,
                            'end_stop_id': end_stop_obj.id,
                        })
                        results.append(segment_data)
                else:
                    error_message = f"No segments found for bus line {bus_line_number}."
            except BusLine.DoesNotExist:
                error_message = "Invalid bus line number entered."
            except Exception as e:
                error_message = f"An error occurred during search: {e}"

    elif search_type == 'buses_by_stop':
        if not single_bus_stop_name_raw:
            error_message = "Please enter a bus stop name."
        else:
            try:
                target_stop = get_bus_stop_object(single_bus_stop_name_raw)

                if not target_stop:
                    error_message = "Invalid bus stop name entered. Please check and try again."
                else:
                    segments_at_stop = RouteSegment.objects.filter(bus_stop=target_stop).select_related(
                        'bus_line').order_by('bus_line__line_number')

                    if not segments_at_stop.exists():
                        error_message = f"No bus lines found for '{target_stop.name_en}'."
                    else:
                        found_bus_lines_info = []
                        processed_bus_lines = set()

                        for segment in segments_at_stop:
                            bus_line = segment.bus_line
                            if bus_line.line_number not in processed_bus_lines:
                                processed_bus_lines.add(bus_line.line_number)

                                all_line_segments = RouteSegment.objects.filter(bus_line=bus_line).order_by(
                                    'order').select_related('bus_stop')
                                line_coords_for_osrm = []
                                for seg in all_line_segments:
                                    if seg.bus_stop.latitude and seg.bus_stop.longitude:
                                        line_coords_for_osrm.append(
                                            (float(seg.bus_stop.latitude), float(seg.bus_stop.longitude)))

                                total_line_distance, total_line_time = get_route_details_from_osrm(line_coords_for_osrm)

                                found_bus_lines_info.append({
                                    'bus_line_number': bus_line.line_number,
                                    'stops_count': all_line_segments.count(),
                                    'total_distance_km': round(total_line_distance,
                                                               2) if total_line_distance is not None else 'N/A',
                                    'total_time_minutes': round(total_line_time,
                                                                0) if total_line_time is not None else 'N/A',
                                    'route_type': 'single_stop_buses_list',
                                    'searched_stop_name': target_stop.name_en,
                                    'target_stop_latitude': float(
                                        target_stop.latitude) if target_stop.latitude else None,
                                    'target_stop_longitude': float(
                                        target_stop.longitude) if target_stop.longitude else None,
                                    'full_line_start_stop_name': all_line_segments.first().bus_stop.name_en if all_line_segments.first() else '',
                                    'full_line_end_stop_name': all_line_segments.last().bus_stop.name_en if all_line_segments.last() else '',
                                })
                        results.extend(sorted(found_bus_lines_info, key=lambda x: x['bus_line_number']))
            except Exception as e:
                error_message = f"An error occurred during search: {e}"

    return render(request, 'search_results.html', {
        'results': results,
        'error_message': error_message,
        'start_stop_name': start_stop_obj.name_en if start_stop_obj else start_stop_name_raw,
        'end_stop_name': end_stop_obj.name_en if end_stop_obj else end_stop_name_raw,
        'bus_line_number': bus_line_number,
        'single_bus_stop_name': single_bus_stop_name_raw,
        'search_type': search_type,
        'start_stop_id': start_stop_obj.id if start_stop_obj else start_stop_id_param,
        'end_stop_id': end_stop_obj.id if end_stop_obj else end_stop_id_param,
        'search_count': search_count,
    })


def get_bus_stops_json(request):
    bus_stops = BusStop.objects.all().values('name_mm', 'name_en', 'road_name_mm', 'road_name_en')
    return JsonResponse(list(bus_stops), safe=False)


def is_admin(user):
    return user.is_authenticated and user.is_staff


@user_passes_test(is_admin)
def admin_dashboard(request):
    bus_stops_count = BusStop.objects.count()
    bus_lines_count = BusLine.objects.count()
    route_segments_count = RouteSegment.objects.count()
    users_count = User.objects.count()

    recent_saved_routes = SavedRoute.objects.all().order_by('-created_at')[:10]
    stops_missing_coords = BusStop.objects.filter(Q(latitude__isnull=True) | Q(longitude__isnull=True))[:10]

    return render(request, 'admin_dashboard.html', {
        'active_tab': 'dashboard',
        'bus_stops_count': bus_stops_count,
        'bus_lines_count': bus_lines_count,
        'route_segments_count': route_segments_count,
        'users_count': users_count,
        'recent_saved_routes': recent_saved_routes,
        'stops_missing_coords': stops_missing_coords
    })


@user_passes_test(is_admin)
def admin_bus_stops(request):
    bus_stops_list = BusStop.objects.all().order_by('name_en')
    paginator = Paginator(bus_stops_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'admin_bus_stops.html', {
        'active_tab': 'bus_stops',
        'bus_stops': page_obj,
        'page_obj': page_obj,
        'paginator': paginator
    })


@user_passes_test(is_admin)
def admin_bus_stop_add(request):
    if request.method == 'POST':
        name_en = request.POST.get('name_en')
        name_mm = request.POST.get('name_mm')
        road_name_en = request.POST.get('road_name_en')
        road_name_mm = request.POST.get('road_name_mm')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')

        if not name_en or not name_mm:
            messages.error(request, 'Name fields are required')
            return render(request, 'admin_bus_stop_form.html', {
                'active_tab': 'bus_stops',
                'form_title': 'Add Bus Stop',
                'form_action': reverse('admin_bus_stop_add'),
                'bus_stop': {
                    'name_en': name_en,
                    'name_mm': name_mm,
                    'road_name_en': road_name_en,
                    'road_name_mm': road_name_mm,
                    'latitude': latitude,
                    'longitude': longitude
                }
            })

        bus_stop = BusStop(
            name_en=name_en,
            name_mm=name_mm,
            road_name_en=road_name_en,
            road_name_mm=road_name_mm
        )

        if latitude and longitude:
            bus_stop.latitude = latitude
            bus_stop.longitude = longitude

        try:
            bus_stop.save()
            messages.success(request, f'Bus stop "{name_en}" added successfully')
            return redirect('admin_bus_stops')
        except Exception as e:
            messages.error(request, f'Error adding bus stop: {str(e)}')

    return render(request, 'admin_bus_stop_form.html', {
        'active_tab': 'bus_stops',
        'form_title': 'Add Bus Stop',
        'form_action': reverse('admin_bus_stop_add')
    })


@user_passes_test(is_admin)
def admin_bus_stop_edit(request, stop_id):
    bus_stop = get_object_or_404(BusStop, id=stop_id)

    if request.method == 'POST':
        bus_stop.name_en = request.POST.get('name_en')
        bus_stop.name_mm = request.POST.get('name_mm')
        bus_stop.road_name_en = request.POST.get('road_name_en')
        bus_stop.road_name_mm = request.POST.get('road_name_mm')

        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')

        if not bus_stop.name_en or not bus_stop.name_mm:
            messages.error(request, 'Name fields are required')
            return render(request, 'admin_bus_stop_form.html', {
                'active_tab': 'bus_stops',
                'form_title': 'Edit Bus Stop',
                'form_action': reverse('admin_bus_stop_edit', args=[stop_id]),
                'bus_stop': bus_stop
            })

        if latitude and longitude:
            bus_stop.latitude = latitude
            bus_stop.longitude = longitude

        try:
            bus_stop.save()
            messages.success(request, f'Bus stop "{bus_stop.name_en}" updated successfully')
            return redirect('admin_bus_stops')
        except Exception as e:
            messages.error(request, f'Error updating bus stop: {str(e)}')

    return render(request, 'admin_bus_stop_form.html', {
        'active_tab': 'bus_stops',
        'form_title': 'Edit Bus Stop',
        'form_action': reverse('admin_bus_stop_edit', args=[stop_id]),
        'bus_stop': bus_stop
    })


@user_passes_test(is_admin)
def admin_bus_stop_delete(request, stop_id):
    bus_stop = get_object_or_404(BusStop, id=stop_id)
    if request.method == 'POST':
        try:
            bus_stop.delete()
            messages.success(request, f'Bus stop "{bus_stop.name_en}" deleted successfully.')
        except Exception as e:
            messages.error(request, f'Error deleting bus stop: {str(e)}')
        return redirect('admin_bus_stops')

    return render(request, 'admin_bus_stop_confirm_delete.html', {
        'active_tab': 'bus_stops',
        'bus_stop': bus_stop
    })


@user_passes_test(is_admin)
def admin_bus_lines(request):
    bus_lines_list = BusLine.objects.all().order_by('line_number')
    paginator = Paginator(bus_lines_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'admin_bus_lines.html', {
        'active_tab': 'bus_lines',
        'bus_lines': page_obj,
        'page_obj': page_obj,
        'paginator': paginator
    })


@user_passes_test(is_admin)
def admin_bus_line_add(request):
    if request.method == 'POST':
        line_number = request.POST.get('line_number')
        description = request.POST.get('description')

        if not line_number:
            messages.error(request, 'Bus Line Number is required.')
            return render(request, 'admin_bus_line_form.html', {
                'active_tab': 'bus_lines',
                'form_title': 'Add Bus Line',
                'form_action': reverse('admin_bus_line_add'),
                'bus_line': {
                    'line_number': line_number,
                    'description': description
                }
            })
        try:
            BusLine.objects.create(line_number=line_number, description=description)
            messages.success(request, f'Bus Line {line_number} added successfully.')
            return redirect('admin_bus_lines')
        except Exception as e:
            messages.error(request, f'Error adding bus line: {e}')

    return render(request, 'admin_bus_line_form.html', {
        'active_tab': 'bus_lines',
        'form_title': 'Add Bus Line',
        'form_action': reverse('admin_bus_line_add')
    })


@user_passes_test(is_admin)
def admin_bus_line_edit(request, line_id):
    bus_line = get_object_or_404(BusLine, id=line_id)

    if request.method == 'POST':
        bus_line.line_number = request.POST.get('line_number')
        bus_line.description = request.POST.get('description')

        if not bus_line.line_number:
            messages.error(request, 'Bus Line Number is required.')
            return render(request, 'admin_bus_line_form.html', {
                'active_tab': 'bus_lines',
                'form_title': 'Edit Bus Line',
                'form_action': reverse('admin_bus_line_edit', args=[line_id]),
                'bus_line': bus_line
            })
        try:
            bus_line.save()
            messages.success(request, f'Bus Line {bus_line.line_number} updated successfully.')
            return redirect('admin_bus_lines')
        except Exception as e:
            messages.error(request, f'Error updating bus line: {e}')

    return render(request, 'admin_bus_line_form.html', {
        'active_tab': 'bus_lines',
        'form_title': 'Edit Bus Line',
        'form_action': reverse('admin_bus_line_edit', args=[line_id]),
        'bus_line': bus_line
    })


@user_passes_test(is_admin)
def admin_bus_line_delete(request, line_id):
    bus_line = get_object_or_404(BusLine, id=line_id)
    if request.method == 'POST':
        try:
            bus_line.delete()
            messages.success(request, f'Bus Line {bus_line.line_number} deleted successfully.')
        except Exception as e:
            messages.error(request, f'Error deleting bus line: {e}')
        return redirect('admin_bus_lines')

    return render(request, 'admin_bus_line_confirm_delete.html', {
        'active_tab': 'bus_lines',
        'bus_line': bus_line
    })


@user_passes_test(is_admin)
def admin_route_segments(request):
    segments_list = RouteSegment.objects.all().order_by('bus_line__line_number', 'order').select_related('bus_line',
                                                                                                         'bus_stop')

    paginator = Paginator(segments_list, 20)  # Show 20 segments per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'admin_route_segments.html', {
        'active_tab': 'route_segments',
        'segments': page_obj
    })


@user_passes_test(is_admin)
def admin_route_segment_add(request):
    bus_lines = BusLine.objects.all().order_by('line_number')
    bus_stops = BusStop.objects.all().order_by('name_en')

    if request.method == 'POST':
        bus_line_id = request.POST.get('bus_line')
        bus_stop_id = request.POST.get('bus_stop')
        order = request.POST.get('order')

        if not bus_line_id or not bus_stop_id or not order:
            messages.error(request, 'All fields are required.')
            return redirect('admin_route_segment_add')

        try:
            bus_line = get_object_or_404(BusLine, id=bus_line_id)
            bus_stop = get_object_or_404(BusStop, id=bus_stop_id)
            RouteSegment.objects.create(bus_line=bus_line, bus_stop=bus_stop, order=order)
            messages.success(request, f'Route segment for {bus_line.line_number} added successfully.')
            return redirect('admin_route_segments')
        except Exception as e:
            messages.error(request, f'Error adding segment: {e}')

    return render(request, 'admin_route_segment_form.html', {
        'active_tab': 'route_segments',
        'form_title': 'Add Route Segment',
        'form_action': reverse('admin_route_segment_add'),
        'bus_lines': bus_lines,
        'bus_stops': bus_stops
    })


@user_passes_test(is_admin)
def admin_route_segment_edit(request, segment_id):
    segment = get_object_or_404(RouteSegment, id=segment_id)
    bus_lines = BusLine.objects.all().order_by('line_number')
    bus_stops = BusStop.objects.all().order_by('name_en')

    if request.method == 'POST':
        segment.bus_line = get_object_or_404(BusLine, id=request.POST.get('bus_line'))
        segment.bus_stop = get_object_or_404(BusStop, id=request.POST.get('bus_stop'))
        segment.order = request.POST.get('order')

        try:
            segment.save()
            messages.success(request, f'Route segment for {segment.bus_line.line_number} updated successfully.')
            return redirect('admin_route_segments')
        except Exception as e:
            messages.error(request, f'Error updating segment: {e}')

    return render(request, 'admin_route_segment_form.html', {
        'active_tab': 'route_segments',
        'form_title': 'Edit Route Segment',
        'form_action': reverse('admin_route_segment_edit', args=[segment_id]),
        'bus_lines': bus_lines,
        'bus_stops': bus_stops,
        'segment': segment
    })


@user_passes_test(is_admin)
def admin_route_segment_delete(request, segment_id):
    segment = get_object_or_404(RouteSegment, id=segment_id)
    if request.method == 'POST':
        try:
            segment.delete()
            messages.success(request, 'Route segment deleted successfully.')
        except Exception as e:
            messages.error(request, f'Error deleting segment: {e}')
        return redirect('admin_route_segments')

    return render(request, 'admin_route_segment_confirm_delete.html', {
        'active_tab': 'route_segments',
        'segment': segment
    })


@user_passes_test(is_admin)
def admin_users(request):
    users_list = User.objects.all().order_by('username')
    paginator = Paginator(users_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'admin_users.html', {
        'active_tab': 'users',
        'users': page_obj
    })


@user_passes_test(is_admin)
def admin_user_edit(request, user_id):
    """Admin view for editing a user."""
    user_to_edit = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        user_to_edit.email = request.POST.get('email', user_to_edit.email)
        user_to_edit.is_staff = request.POST.get('is_staff') == 'on'
        user_to_edit.is_superuser = request.POST.get('is_superuser') == 'on'
        try:
            user_to_edit.save()
            messages.success(request, f'User {user_to_edit.username} updated successfully.')
            return redirect('admin_users')
        except Exception as e:
            messages.error(request, f'Error updating user: {e}')

    return render(request, 'admin_user_form.html', {
        'active_tab': 'users',
        'form_title': 'Edit User',
        'form_action': reverse('admin_user_edit', args=[user_id]),
        'user_obj': user_to_edit
    })


@user_passes_test(is_admin)
def admin_user_delete(request, user_id):
    user_to_delete = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        try:
            user_to_delete.delete()
            messages.success(request, f'User {user_to_delete.username} deleted successfully.')
        except Exception as e:
            messages.error(request, f'Error deleting user: {e}')
        return redirect('admin_users')

    return render(request, 'admin_user_confirm_delete.html', {
        'active_tab': 'users',
        'user_obj': user_to_delete
    })


@user_passes_test(is_admin)
def admin_saved_routes(request):
    saved_routes_list = SavedRoute.objects.all().order_by('-created_at')
    paginator = Paginator(saved_routes_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'admin_saved_routes.html', {
        'active_tab': 'saved_routes',
        'saved_routes': page_obj
    })


@user_passes_test(is_admin)
def admin_saved_route_edit(request, route_id):
    saved_route = get_object_or_404(SavedRoute, id=route_id)
    bus_stops = BusStop.objects.all().order_by('name_en')

    if request.method == 'POST':
        saved_route.name = request.POST.get('name')
        saved_route.start_stop = get_object_or_404(BusStop, id=request.POST.get('start_stop'))
        saved_route.end_stop = get_object_or_404(BusStop, id=request.POST.get('end_stop'))
        saved_route.line_number = request.POST.get('line_number')

        try:
            saved_route.save()
            messages.success(request, f'Saved route "{saved_route.name}" updated successfully.')
            return redirect('admin_saved_routes')
        except Exception as e:
            messages.error(request, f'Error updating saved route: {e}')

    return render(request, 'admin_saved_route_form.html', {
        'active_tab': 'saved_routes',
        'form_title': 'Edit Saved Route',
        'form_action': reverse('admin_saved_route_edit', args=[route_id]),
        'saved_route': saved_route,
        'bus_stops': bus_stops
    })


@user_passes_test(is_admin)
def admin_saved_route_delete(request, route_id):
    saved_route = get_object_or_404(SavedRoute, id=route_id)
    if request.method == 'POST':
        try:
            saved_route.delete()
            messages.success(request, f'Saved route "{saved_route.name}" deleted successfully.')
        except Exception as e:
            messages.error(request, f'Error deleting saved route: {e}')
        return redirect('admin_saved_routes')

    return render(request, 'admin_saved_route_confirm_delete.html', {
        'active_tab': 'saved_routes',
        'saved_route': saved_route
    })


def all_bus_lines(request):
    bus_lines = BusLine.objects.all().order_by('line_number')
    context = {'bus_lines': bus_lines}
    return render(request, 'all_bus_lines.html', context)


def bus_line_route_api(request, bus_line_id):
    """
    Retrieves the route segments for a specific bus line and returns them as a JSON response.
    The segments are ordered by their 'order' field to represent the correct sequence of the route.
    """
    try:
        route_segments = RouteSegment.objects.filter(bus_line_id=bus_line_id).order_by('order')

        data = []
        for segment in route_segments:
            data.append({
                'id': segment.id,
                'order': segment.order,
                'start_stop_name_mm': segment.start_stop.name_mm if segment.start_stop else None,
                'end_stop_name_mm': segment.end_stop.name_mm if segment.end_stop else None,
            })
        return JsonResponse(data, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def rangoon_map(request):
    context = {}
    return render(request, 'rangoon_map.html', context)


def complaint_numbers(request):
    bus_lines = BusLine.objects.all().order_by('line_number')
    context = {'bus_lines': bus_lines}
    return render(request, 'complaint_numbers.html', context)


def get_complaint_numbers_api(request, line_number):
    """
    Returns complaint numbers for a specific bus line as JSON.
    For demonstration, hardcoded data is used. In a real app, this would come from a DB.
    """
    complaint_data = {
        'YBS 1': {
            'Yangon Region Transport Committee (YRTC)': ['09 448147149', '09 448147153', '09 448147154'],
            'Golden Yangon City Transportation Public Co.,Ltd (GYCT)': ['09 443144471', '09 428045840', '09 683011360']
        },
        'YBS 11': {
            'Yangon Region Transport Committee (YRTC)': ['09 448147149', '09 448147153', '09 448147154'],
            'Yangon Urban Public Transportation Public Co.,Ltd (YUPT)': ['09 454546655', '09 964546655', '09-5119579']
        },
        'YBS 66': {
            'Yangon Region Transport Committee (YRTC)': ['09 448147149', '09 448147153', '09 448147154'],
            'Rapid City Bus Transportation Public Co.,Ltd (RCBT)': ['09-5094551', '09 250686431', '09 459777784', '09 443672582']
        },
        'YBS 78': {
            'Yangon Region Transport Committee (YRTC)': ['09 448147149', '09 448147153', '09 448147154'],
            'Ludu Partners Public Co.,Ltd (LUDU)': ['09 685208016', '09 776124365']
        },
        'YBS 94': {
            'Yangon Region Transport Committee (YRTC)': ['09 448147149', '09 448147153', '09 448147154'],
            'Ludu Partners Public Co.,Ltd (LUDU)': ['09 685208016', '09 776124365']
        },
        'YBS 14': {
            'Yangon Region Transport Committee (YRTC)': ['09 448147149', '09 448147153', '09 448147154'],
            'Bandoola Transport Public Co.,Ltd(BDL)': ['09 73023290', '09 773027939', '09 26289646']
        },
        'YBS 61': {
            'Yangon Region Transport Committee (YRTC)': ['09 448147149', '09 448147153', '09 448147154'],
            'Khit Thit Bayint Naung Public Co.,Ltd (KTB)': ['09 43098386', '09 972074499', '09 455798875',
                                                                    '09 795521586']
        },
        'YBS 131': {
            'Yangon Region Transport Committee (YRTC)': ['09 448147149', '09 448147153', '09 448147154'],
            'Powe Eleven Public Co.,Ltd (POWER ELEVEN)': ['09 5062382', '09 456060069', '09 456060096',
                                                            '09 466060099']
        },
    }

    numbers = complaint_data.get(line_number, {})
    return JsonResponse(numbers, safe=False)


def bus_lines_api(request):
    """
    Retrieves all bus lines from the database and returns them as a JSON response.
    This function is used by the frontend to dynamically load the bus line data.
    """
    try:
        bus_lines = BusLine.objects.all()
        data = []
        for bus in bus_lines:
            data.append({
                'bus_no': bus.line_number,
                'description': bus.description
            })
        return JsonResponse(data, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def bus_stops_api(request):
    try:
        bus_stops = BusStop.objects.all()
        data = serializers.serialize('json', bus_stops)
        return JsonResponse(json.loads(data), safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='login')
def all_bus_lines_view(request):
    return render(request, 'all_bus_lines.html')

def complaints_view(request):
    """
    Renders the complaints page and fetches all complaints from the database.
    """
    complaints = Complaint.objects.all().order_by('-created_at')
    context = {
        'complaints': complaints,
        'active_tab': 'complaints'
    }
    return render(request, 'admin_complaints.html', context)



def submit_complaint_view(request):
    """
    Handles the submission of a new complaint from the modal form.
    Validates that the submitted email matches the authenticated user's email.
    """
    # Check if the user is authenticated (logged in)
    if not request.user.is_authenticated:
        # Return JSON response for unauthenticated users
        return JsonResponse(
            {"success": False, "error": "Please log in to submit a complaint.", "redirect_url": reverse('login')})

    email = request.POST.get('user_email')
    line_number = request.POST.get('line_number')
    message = request.POST.get('message')

    # Basic validation for all fields
    if not email or not line_number or not message:
        return JsonResponse({"success": False, "error": "All fields are required."})

    # Compare the submitted email with the logged-in user's email
    if email != request.user.email:
        # Return a more user-friendly and specific error message
        return JsonResponse({"success": False,
                             "error": "Your submitted email does not match the email associated with your logged-in account. Please make sure you are using the correct email."})

    try:
        bus_line = BusLine.objects.get(line_number=line_number.replace('YBS ', ''))
        Complaint.objects.create(email=email, bus_line=bus_line, message=message)
        # Return success JSON response
        return JsonResponse({"success": True, "message": "Your complaint has been submitted successfully."})

    except BusLine.DoesNotExist:
        # This case should ideally not happen based on the front-end logic
        return JsonResponse({"success": False, "error": "The specified bus line does not exist."})

    except Exception as e:
        return JsonResponse({"success": False, "error": f"An error occurred: {e}"})
