import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';

@Injectable({
  providedIn: 'root'
})
export class ImagesService {

  baseUrl: string = "http://127.0.0.1:8000/"

  constructor(private httpClient: HttpClient) { }

  public getAllImages() {
    return this.httpClient.get(this.baseUrl + 'web/images'
    );
  }

  public getImageByThumbnail(name: string) {
    return this.httpClient.get(this.baseUrl + 'web/image_by_thumbnail' + '?name=' + name, {
      responseType: 'blob'
    });
  }

  public getImagesByStack(ext: string) {
    return this.httpClient.get(this.baseUrl + 'web/images_by_stack' + '?ext=' + ext);
  }

  public getFFTImageByName(name: string) {
    return this.httpClient.get(this.baseUrl + 'web/fft_image' + '?name=' + name, {
      responseType: 'blob'
    });
  }

  public getImageDataByName(name: string) {
    return this.httpClient.get(this.baseUrl + 'web/image_data' + '?name=' + name);
  }
}
