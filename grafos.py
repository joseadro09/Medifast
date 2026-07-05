import osmnx as ox
import heapq
import math
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# =========================================================================
# CONFIGURACIÓN DE FASTAPI Y GRAFO BASE
# =========================================================================
app = FastAPI(title="API de Optimización Logística CENARES", version="1.0.0")

# Permitir que Angular (u otros frontends) se conecten sin bloqueos de seguridad CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # En producción cambiar por la URL de Angular
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("Descargando red vial de San Miguel y Pueblo Libre...")
lugares = ["San Miguel, Lima, Peru", "Pueblo Libre, Lima, Peru"]

# NUEVO: Filtro estricto para evitar zonas en construcción y accesos privados
filtro_estricto = (
    '["area"!~"yes"]'
    '["highway"!~"construction|proposed|abandoned"]'
    '["access"!~"private|no|customers"]'
)

G = ox.graph_from_place(lugares, network_type="drive", custom_filter=filtro_estricto)

tags = {'amenity': ['hospital', 'pharmacy', 'clinic', 'doctors']}
centros_salud = ox.features_from_place(lugares, tags)

nodos_salud = set()
for idx, row in centros_salud.iterrows():
    geom = row.geometry
    if geom.geom_type in ['Polygon', 'MultiPolygon']:
        x, y = geom.centroid.x, geom.centroid.y
    else:
        x, y = geom.x, geom.y
    nodo = ox.distance.nearest_nodes(G, X=x, Y=y)
    nodos_salud.add(nodo)

# Origen fijo: CENARES
coord_cenares = (-12.0780, -77.0920) 
nodo_cenares = ox.distance.nearest_nodes(G, X=coord_cenares[1], Y=coord_cenares[0])
print("¡Grafo listo y escuchando peticiones!")

nodos_df, aristas_df = ox.graph_to_gdfs(G)
print("\n--- DATASET DE ARISTAS (CALLES) ---")
print(aristas_df[['length', 'highway']].head())
print("-----------------------------------\n")

print("¡Grafo listo y escuchando peticiones!")

# =========================================================================
# FUNCIONES MATEMÁTICAS Y ALGORÍTMICAS (Pasos 1 y 2)
# =========================================================================

def calcular_peso_dinamico(grafo, u, v, hora):
    datos_arista = grafo.edges[u, v, 0]
    distancia_base = datos_arista.get('length', 1.0)
    tipo_via = datos_arista.get('highway', 'residential')
    
    es_avenida = False
    if isinstance(tipo_via, list):
        es_avenida = any(v in ['primary', 'secondary', 'tertiary', 'trunk'] for v in tipo_via)
    else:
        es_avenida = tipo_via in ['primary', 'secondary', 'tertiary', 'trunk']
        
    if 6 <= hora < 9 or 17 <= hora < 21:  # Hora Punta
        factor = 3.5 if es_avenida else 1.5
    elif 9 <= hora < 17 or 21 <= hora < 24: # Hora Valle
        factor = 1.8 if es_avenida else 1.1
    else:  # Madrugada
        factor = 1.0
        
    return distancia_base * factor

def heuristica_haversine(nodo_actual, nodo_destino, grafo):
    lat1, lon1 = grafo.nodes[nodo_actual]['y'], grafo.nodes[nodo_actual]['x']
    lat2, lon2 = grafo.nodes[nodo_destino]['y'], grafo.nodes[nodo_destino]['x']
    R = 6371000.0 
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def ejecutar_busqueda(grafo, origen, destino, hora, tipo_algoritmo):
    queue = []
    heapq.heappush(queue, (0, origen))
    costos_g = {nodo: float('inf') for nodo in grafo.nodes}
    costos_g[origen] = 0
    padres = {origen: None}
    nodos_visitados = 0
    
    while queue:
        f_actual, u = heapq.heappop(queue)
        nodos_visitados += 1
        
        if u == destino:
            break
            
        for v in grafo.neighbors(u):
            peso_ponderado = calcular_peso_dinamico(grafo, u, v, hora)
            nuevo_costo_g = costos_g[u] + peso_ponderado
            
            if nuevo_costo_g < costos_g[v]:
                costos_g[v] = nuevo_costo_g
                padres[v] = u
                h = heuristica_haversine(v, destino, grafo) if tipo_algoritmo == "A*" else 0
                f = nuevo_costo_g + h
                heapq.heappush(queue, (f, v))
                
    camino = []
    actual = destino
    if actual in padres or actual == origen:
        while actual is not None:
            camino.append(actual)
            actual = padres[actual]
        camino.reverse()
        
    return camino, costos_g[destino], nodos_visitados

# =========================================================================
# ENDPOINTS DE LA API (PASO 3)
# =========================================================================

@app.get("/api/salud")
def obtener_puntos_salud():
    """Retorna las coordenadas de todos los hospitales/farmacias y de CENARES para pintarlos en el mapa web."""
    destinos = []
    for nodo in nodos_salud:
        destinos.append({
            "id": int(nodo),
            "lat": float(G.nodes[nodo]['y']),
            "lon": float(G.nodes[nodo]['x']),
            "tipo": "hospital"
        })
    
    return {
        "origen": {
            "id": int(nodo_cenares),
            "lat": float(G.nodes[nodo_cenares]['y']),
            "lon": float(G.nodes[nodo_cenares]['x']),
            "tipo": "cenares"
        },
        "destinos": destinos
    }

@app.get("/api/ruta")
def obtener_ruta_optima(destino_id: int, hora: int, algoritmo: str = "A*"):
    """Calcula la ruta óptima dinámicamente y la devuelve formateada en coordenadas GPS."""
    if destino_id not in G.nodes:
        raise HTTPException(status_code=404, detail="El nodo de destino no existe en la red vial.")
        
    if algoritmo not in ["Dijkstra", "A*"]:
        raise HTTPException(status_code=400, detail="Algoritmo no soportado. Use 'Dijkstra' o 'A*'.")

    # Ejecutar motor algorítmico
    camino_nodos, costo, visitados = ejecutar_busqueda(G, nodo_cenares, destino_id, hora, algoritmo)
    
    if not camino_nodos:
        raise HTTPException(status_code=404, detail="No se encontró una ruta viable.")

    # Transformar los IDs de los nodos en coordenadas lat/lon legibles por el mapa web
    coordenadas_ruta = [[float(G.nodes[nodo]['y']), float(G.nodes[nodo]['x'])] for nodo in camino_nodos]
    
    # Transformar los IDs de los nodos en coordenadas lat/lon
    coordenadas_ruta = [[float(G.nodes[nodo]['y']), float(G.nodes[nodo]['x'])] for nodo in camino_nodos]
    
# NUEVO: Calcular tiempo estimado en minutos y segundos reales
    velocidad_promedio_ms = 8.33 # 30 km/h
    tiempo_segundos = costo / velocidad_promedio_ms
    
    # Usamos división entera (//) para los minutos y módulo (%) para los segundos
    minutos = int(tiempo_segundos // 60)
    segundos = int(tiempo_segundos % 60)
    
    # Creamos un texto formateado
    tiempo_formateado = f"{minutos} min y {segundos} seg"
    
    return {
        "algoritmo_usado": algoritmo,
        "costo_total": round(costo, 2),
        "nodos_evaluados": visitados,
        "tiempo_estimado": tiempo_formateado, # Ahora enviamos un texto, no un número
        "coordenadas": coordenadas_ruta
    }

# Arrancar el servidor web si se ejecuta el archivo directamente
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)