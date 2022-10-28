import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';

@Injectable({
  providedIn: 'root'
})
export class ImagesService {

  baseUrl: string = "http://127.0.0.1:5000/"

  constructor(private httpClient: HttpClient) { }

  public getAllImages() {
    return this.httpClient.get(this.baseUrl + 'get_images'
    );
  }

  public getImageByThumbnail(name: string) {
    return this.httpClient.get(this.baseUrl + 'get_image_by_thumbnail' + '?name=' + name, {
      responseType: 'blob'
    });
  }

  public getImagesByStack(ext: string) {
    return this.httpClient.get(this.baseUrl + 'get_images_by_stack' + '?ext=' + ext);
  }
}
