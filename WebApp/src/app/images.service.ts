import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';

@Injectable({
  providedIn: 'root'
})
export class ImagesService {

  baseUrl: string = "http://127.0.0.1:8000/web/"

  constructor(private httpClient: HttpClient) { }

  public getAllImages() {
    return this.httpClient.get(this.baseUrl + 'images'
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

}
