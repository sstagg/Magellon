import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';

import { environment } from '../environments/environment';
@Injectable({
  providedIn: 'root'
})
export class ImagesService {

  baseUrl: string = environment.apiUrl;
  // baseUrl: string = "http://127.0.0.1:8000/web/"

  constructor(private httpClient: HttpClient) { }

  public getAllImages(session_name: string, level: number) {
    return this.httpClient.get(this.baseUrl + 'images' + '?session_name=' + session_name + '&' + 'level=' + level
    );
  }

  public getImageByThumbnail(name: string) {
    return this.httpClient.get(this.baseUrl + 'image_by_thumbnail' + '?name=' + name, {
      responseType: 'blob'
    });
  }

  public getImagesByStack(ext: string) {
    return this.httpClient.get(this.baseUrl + 'images_by_stack' + '?ext=' + ext);
  }

  public getFFTImageByName(name: string) {
    return this.httpClient.get(this.baseUrl + 'fft_image' + '?name=' + name, {
      responseType: 'blob'
    });
  }

  public getImageDataByName(name: string) {
    return this.httpClient.get(this.baseUrl + 'image_data' + '?name=' + name);
  }

  public getParticles(name: string) {
    return this.httpClient.get(this.baseUrl + 'particles' + '?img_name=' + name);
  }

  public getParticlesByOid(oid: string) {
    return this.httpClient.get(this.baseUrl + 'particles' + '/' + oid);
  }

  public updateParticlesByOid(oid: string, reqbody: any) {
    return this.httpClient.put(this.baseUrl + 'particles' + '/' + oid, reqbody);
  }
  
  public getSessions(name: string) {
    return this.httpClient.get(this.baseUrl + 'sessions' + '?name=' + name);
  }
}