import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class LogisticaService {
  private apiUrl = 'http://127.0.0.1:8000/api';

  constructor(private http: HttpClient) { }

  getPuntosSalud(): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/salud`);
  }

  getCalculoRuta(destinoId: number, hora: number, algoritmo: string): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/ruta?destino_id=${destinoId}&hora=${hora}&algoritmo=${algoritmo}`);
  }
}