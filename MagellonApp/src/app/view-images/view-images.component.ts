import { Component, OnInit } from '@angular/core';
import { ImagesService } from '../images.service';
import { DomSanitizer } from '@angular/platform-browser';

export interface ImageModel {
  name: string;
  encoded_image: string;
  url: any;
  ext: string;
}

export interface ImageExtModel {
  ext: string;
  images: any;
}

export interface ImageSpec {
  defocus : string
  mag: string
  filename: string
  pixelsize: string
  dose: string
}

@Component({
  selector: 'app-view-images',
  templateUrl: './view-images.component.html',
  styleUrls: ['./view-images.component.css']
})

export class ViewImagesComponent implements OnInit {
  imageUrl: any;
  fftImageUrl: any;
  enableFFT: boolean = false;
  unsafeImageUrl: any;
  imageIdx: number = 0;
  extIdx: number = 0;
  imageModelArr: ImageExtModel[] = [];
  imageStackModelArr: ImageExtModel[] = [];
  unstackDisplay: boolean[] = [];
  imageName: string = "";
  imageSpec: ImageSpec = {
    defocus: '',
    mag: '',
    filename: '',
    pixelsize: '',
    dose: ''
  };
  imageScale : number = 0;
  imageScalePixel : number = 0;
  imageScaleInAngstrom : boolean = false;


  constructor(private imageService: ImagesService, private sanitizer: DomSanitizer) { }

  ngOnInit(): void {

    this.imageService.getAllImages()
      .subscribe((data: any) => {
        for (var i in data.result) {
          let imageExtArr: ImageModel[] = [];
          for (var idx in data.result[i].images) {

            this.unsafeImageUrl = 'data:image/png;base64,' + data.result[i].images[idx].encoded_image;

            // Build ImageModel
            let imageModel = {
              name: data.result[i].images[idx].name,
              encoded_image: data.result[i].images[idx].encoded_image,
              url: this.sanitizer.bypassSecurityTrustUrl(this.unsafeImageUrl),
              ext: data.result[i].ext
            }

            imageExtArr.push(imageModel);
          }

          // Build parent Image model
          let imageExtModel = {
            ext: data.result[i].ext,
            images: imageExtArr
          }
          this.imageModelArr.push(imageExtModel)
        }
        this.getDefaultCenterImage(0, 0);
        this.extIdx = 0;
      })

  }

  getDefaultCenterImage(extIndex: number, imageIndex: number): void {
    this.imageIdx = imageIndex;
    this.extIdx = extIndex;
    this.imageName = this.imageModelArr[extIndex].images[imageIndex].name;
    this.imageName = this.imageName.replace(/_TIMG/, '')
    this.getCenterImage(this.imageName);
  }

  passUnstackImgIndex(imageIndex: number): void {
    this.imageName = this.imageStackModelArr[0].images[imageIndex].name;
    this.imageName = this.imageName.replace(/_TIMG/, '')
    this.getCenterImage(this.imageName);
    this.getFFTImage();
  }

  getCenterImage(imageName: any): void {
    this.imageService.getImageByThumbnail(imageName)
      .subscribe((data: any) => {
        this.unsafeImageUrl = URL.createObjectURL(data);
        this.imageUrl = this.sanitizer.bypassSecurityTrustUrl(this.unsafeImageUrl);
      })
     this.getImageDataByName();
  }

  showUnstack(index: number) {
    this.unstackDisplay = [];
    this.unstackDisplay[index] = true;
  }

  getStackImages(ext: any) {
    this.imageStackModelArr = [];
    this.imageService.getImagesByStack(ext)
      .subscribe((data: any) => {
        let imageStackExtArr: ImageModel[] = [];
        for (var idx in data.result[0].images) {

          this.unsafeImageUrl = 'data:image/png;base64,' + data.result[0].images[idx].encoded_image;

          // Build ImageModel
          let imageModel = {
            name: data.result[0].images[idx].name,
            encoded_image: data.result[0].images[idx].encoded_image,
            url: this.sanitizer.bypassSecurityTrustUrl(this.unsafeImageUrl),
            ext: data.result[0].ext
          }

          imageStackExtArr.push(imageModel);
        }

        // Build parent Image model
        let imageStackExtModel = {
          ext: data.result[0].ext,
          images: imageStackExtArr
        }
        this.imageStackModelArr[0] = imageStackExtModel;
      })
  }

  getFFTImage(): void {
    this.imageService.getFFTImageByName(this.imageName)
      .subscribe((data: any) => {
        this.unsafeImageUrl = URL.createObjectURL(data);
        this.fftImageUrl = this.sanitizer.bypassSecurityTrustUrl(this.unsafeImageUrl);
      })
  }

  getFFTImageOnToggle(): void {
    this.enableFFT = !this.enableFFT;
    if (this.enableFFT) {
      this.getFFTImage();
    }
  }

  // Get image specifications like defocus, magnification
  getImageDataByName() : void {
    this.imageService.getImageDataByName(this.imageName)
    .subscribe((data: any) => {
      this.imageSpec['defocus'] = data.result.defocus
      this.imageSpec['mag'] = data.result.mag
      this.imageSpec['filename'] = data.result.filename + '.mrc'
      this.imageSpec['pixelsize'] = data.result.pixelsize
      this.imageSpec['dose'] = data.result.dose
      this.imageScale = Math.round((1024 * 0.1 * (data.result.pixelsize))/ 4)
      this.imageScaleInAngstrom = this.imageScale < 1000 ? true : false
      this.imageScalePixel = Math.round(this.imageScale / ((data.result.pixelsize)* 0.1))
      this.imageScale = this.imageScale < 1000 ? this.imageScale * 10 : this.imageScale
      console.log("imageScale : " + this.imageScale)
      console.log("imageScalePixel : " + this.imageScalePixel)
    })
   }
}
