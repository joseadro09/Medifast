import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { LogisticaService } from './servicios/logistica'; 
import * as L from 'leaflet';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.html',
  styleUrls: ['./app.css']    
})
export class AppComponent implements OnInit {
  horaSeleccionada: number = 18; 
  usarHoraReal: boolean = false; // Variable de control para la hora automática
  algoritmoSeleccionado: string = 'A*';
  destinoSeleccionadoId: number | null = null;
  
  nodosEvaluados: number = 0;
  costoTotal: number = 0;
tiempoEstimado: string = '0 min y 0 seg';

  private map!: L.Map;
  private rutaLayer!: L.Polyline;

  constructor(private logisticaService: LogisticaService) {}

  ngOnInit(): void {
    this.inicializarMapa();
    this.cargarCapaPuntos();
  }

  private inicializarMapa(): void {
    this.map = L.map('mapa-contenedor').setView([-12.0780, -77.0850], 14);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18,
      attribution: '© OpenStreetMap contributors'
    }).addTo(this.map);
  }

  private cargarCapaPuntos(): void {
    this.logisticaService.getPuntosSalud().subscribe((data: any) => {
      const iconoCenares = L.divIcon({ 
        className: 'marcador-cenares', 
        html: '<div style="background-color: blue; width: 12px; height: 12px; border-radius: 50%; border: 2px solid white;"></div>' 
      });
      L.marker([data.origen.lat, data.origen.lon], { icon: iconoCenares })
       .addTo(this.map)
       .bindPopup('<b>Punto de Acopio Central: CENARES</b>');

      const iconoHospital = L.divIcon({ 
        className: 'marcador-hospital', 
        html: '<div style="background-color: red; width: 10px; height: 10px; border-radius: 50%; border: 1px solid white;"></div>' 
      });
      
      data.destinos.forEach((destino: any) => {
        const marker = L.marker([destino.lat, destino.lon], { icon: iconoHospital }).addTo(this.map);
        
        marker.on('click', () => {
          this.destinoSeleccionadoId = destino.id;
          marker.bindPopup(`<b>Establecimiento de Salud (Nodo: ${destino.id})</b><br>Listo para optimizar ruta.`).openPopup();
        });
      });
    });
  }

  public calcularRuta(): void {
    if (!this.destinoSeleccionadoId) {
      alert('Por favor, haz clic sobre un punto rojo en el mapa primero.');
      return;
    }

    // APLICACIÓN DE HORA REAL: Si el checkbox está marcado, extraemos la hora actual del sistema
    let horaEnvio = this.horaSeleccionada;
    if (this.usarHoraReal) {
      const ahora = new Date();
      horaEnvio = ahora.getHours(); // Devuelve un entero entre 0 y 23
      console.log(`Hora real del sistema detectada: ${horaEnvio}:00 hrs`);
    }

    this.logisticaService.getCalculoRuta(this.destinoSeleccionadoId, horaEnvio, this.algoritmoSeleccionado)
      .subscribe((res: any) => {
        this.nodosEvaluados = res.nodos_evaluados;
        this.costoTotal = res.costo_total;
        this.tiempoEstimado = res.tiempo_estimado;
        if (this.rutaLayer) {
          this.map.removeLayer(this.rutaLayer);
        }

        this.rutaLayer = L.polyline(res.coordenadas, { color: '#00ff00', weight: 5, opacity: 0.8 }).addTo(this.map);
        this.map.fitBounds(this.rutaLayer.getBounds());
      });
  }
}