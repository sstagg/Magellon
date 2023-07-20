import { Component, OnInit, ViewChild, ElementRef } from '@angular/core';
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
  defocus: string
  mag: string
  filename: string
  pixelsize: string
  dose: string
}

export interface Particle {
  x: number
  y: number
  score: string
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
  unsafeFFTImageUrl: any;
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
  defaultImageSpec: ImageSpec = {
    defocus: '',
    mag: '',
    filename: '',
    pixelsize: '',
    dose: ''
  };
  imageScale: number = 0;
  imageScalePixel: number = 0;
  imageScaleInAngstrom: boolean = false;
  canvas: any;
  ctx: any;
  pointSize: number = 18;
  element: Element;
  root: Element;

  particlePickJobType: any;
  pickType: string;
  selectedPicker = "Select"
  pickTypeEnable: boolean = false
  particlePickCoordinates: Particle[] = []

  allSessions: any;
  selectedSessionOid: string;
  selectedSessionName: string;
  selectedLevel: number;
  allLevels: {[key: number] : string} = {
    1: "level1",
    2: "level2",
    3: "level3",
    4: "level4",
    5: "level5",
    6: "level6"
  }

  constructor(private imageService: ImagesService, private sanitizer: DomSanitizer) { }

  ngOnInit(): void {
    this.getSessions();
    this.selectedSessionName = this.allSessions[this.selectedSessionOid];
    this.selectedLevel = 1;
    this.loadThumbnailsBySession();
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
        this.setCanvasBackground()
        this.imageUrl = this.sanitizer.bypassSecurityTrustUrl(this.unsafeImageUrl);
      })
    this.getImageDataByName();
    this.setParticleJob();
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
        this.unsafeFFTImageUrl = URL.createObjectURL(data);
        this.fftImageUrl = this.sanitizer.bypassSecurityTrustUrl(this.unsafeFFTImageUrl);
      })
  }

  getFFTImageOnToggle(): void {
    this.enableFFT = !this.enableFFT;
    if (this.enableFFT) {
      this.getFFTImage();
      this.pickTypeEnable = true;
    } else {
      this.pickTypeEnable = false;
      this.getCenterImage(this.imageName);
      this.drawParticlesByOid();
    }
  }

  // Get image specifications like defocus, magnification
  getImageDataByName(): void {
    this.imageService.getImageDataByName(this.imageName)
      .subscribe((data: any) => {
        this.imageSpec['defocus'] = data.result.defocus
        this.imageSpec['mag'] = data.result.mag
        this.imageSpec['filename'] = data.result.filename + '.mrc'
        this.imageSpec['pixelsize'] = data.result.PixelSize
        this.imageSpec['dose'] = data.result.dose
        this.imageScale = Math.round((1024 * 0.1 * (data.result.PixelSize)) / 4)
        this.imageScaleInAngstrom = this.imageScale < 1000 ? true : false
        this.imageScalePixel = Math.round(this.imageScale / ((data.result.PixelSize) * 0.1))
        this.imageScale = this.imageScale < 1000 ? this.imageScale * 10 : this.imageScale
        console.log("imageScale : " + this.imageScale)
        console.log("imageScalePixel : " + this.imageScalePixel)
      })
  }

  setParticleJob(): void {
    this.imageService.getParticles(this.imageName)
      .subscribe((data: any) => {
        this.particlePickJobType = {}
        for (var i in data) {
          this.particlePickJobType[data[i].Oid]= data[i].job_name
        }
      })
  }

  drawParticlesByOid(): void {
    this.imageService.getParticlesByOid(this.selectedPicker)
      .subscribe((data: any) => {
        this.clearCanvas()
        const img_cor: { x: number, y: number, score: string }[] = data.particles
        this.pointSize = data.rad
        img_cor.forEach(ele => {
          this.drawCoordinates(ele.x, ele.y, ele.score)
        })
      })
  }

  pickDropdownUpdate(e: any) {
    this.selectedPicker = e.target.value
    this.particlePickCoordinates = []
    if (this.selectedPicker == "default") {
      this.clearCanvas()
    } else {
      this.drawParticlesByOid()
    }
  }

  // Save particle picks into database
  savePicks(): void {
    const reqbody = { "particles": this.particlePickCoordinates, "rad": this.pointSize }
    this.imageService.updateParticlesByOid(this.selectedPicker, reqbody)
      .subscribe((data: any) => {
        console.log(this.selectedPicker)
      })

  }

  resetPicks(): void {
    this.drawParticlesByOid();
  }

  setCanvasBackground(): void {
    this.canvas = <HTMLCanvasElement>document.getElementById("canvas");
    let bg = `url(${this.unsafeImageUrl})`
    this.canvas.style.backgroundImage = bg
    this.canvas.style.backgroundSize = "760px 760px"
    this.ctx = this.canvas.getContext("2d");
  }

  //Set canvas to default
  clearCanvas(): void {
    const context = this.canvas.getContext('2d');
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
  }

  //Get x and y coordinates on canvas on user click, with top left corner of center image as (0,0)
  getPosition(event: any) {

    this.element = <Element>this.root;
    this.canvas = <HTMLCanvasElement>document.getElementById("canvas");

    this.setCanvasBackground()

    let curleft = 0,
      curtop = 0;

    curleft += event.offsetX;
    curtop += event.offsetY;
    this.drawCoordinates(curleft, curtop, "None");
  }

  //Draw a circle around particles
  drawCoordinates(x: any, y: any, score: string) {
    let particle = {
      x: x,
      y: y,
      score: score
    }
    this.particlePickCoordinates.push(particle)

    this.canvas = <HTMLCanvasElement>document.getElementById("canvas");
    this.ctx = this.canvas.getContext("2d");
    const grd = this.ctx.createLinearGradient(0, 0, 170, 0);
    grd.addColorStop(0, "black");
    grd.addColorStop(1, "red");
    this.ctx.strokeStyle = 'rgb(255,0,0, 0.3)';
    this.ctx.lineWidth = 5

    this.ctx.beginPath();
    this.ctx.arc(Number(x), Number(y), this.pointSize, 0, Math.PI * 2, true);
    this.ctx.stroke();

    const coord = "x=" + x + ", y=" + y;
    const p = this.ctx.getImageData(x, y, 1, 1).data;
    const hex = "#" + ("000000" + this.rgbToHex(p[0], p[1], p[2])).slice(-6);
    console.log(hex);
  }

  rgbToHex(r: any, g: any, b: any) {
    if (r > 255 || g > 255 || b > 255)
      throw "Invalid color component";
    return ((r << 16) | (g << 8) | b).toString(16);
  }

  //Get all available sessions
  getSessions(): void {
    this.imageService.getSessions("")
      .subscribe((data: any) => {
        this.allSessions = {}
        this.selectedSessionOid = data[0].Oid;
        this.selectedLevel = 1;
        for (var i in data) {
          this.allSessions[data[i].Oid]= data[i].name;
        }
      })
  }

  // Action on selecting session
  sessionUpdate(e: any) {
    this.selectedSessionOid = e.target.value;
    this.selectedLevel = 1;
    this.selectedSessionName = this.allSessions[this.selectedSessionOid];
    this.loadThumbnailsBySession();
  }

  //Populate thumnail stack for a session
  loadThumbnailsBySession() : void {
    this.imageService.getAllImages(this.selectedSessionName, this.selectedLevel)
      .subscribe((data: any) => {
        if(data.result.length == 0){
          this.imageModelArr = [];
          Object.assign(this.imageSpec, this.defaultImageSpec);
          return;
        }
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
    
  // Action on selecting session level
  levelUpdate(e: any) {
    this.selectedLevel = e.target.value;
    this.selectedSessionName = this.allSessions[this.selectedSessionOid];
    this.loadThumbnailsBySession();
  }

}
