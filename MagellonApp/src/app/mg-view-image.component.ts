import { Component } from "@angular/core";

export interface Tile {
    color: string;
    cols: number;
    rows: number;
    text: string;
  }
  
@Component({
    selector: 'mg-view-image',
    templateUrl: './mg-view-image.component.html',
    styleUrls: ['./mg-view-image.component.css']
})

export class MgViewImageComponent {

    tiles: Tile[] = [
        {text: 'one', cols: 1, rows: 1, color: 'lightgray'},
        {text: 'two', cols: 1, rows: 1, color: 'white'},
        {text: 'three', cols: 1, rows: 1, color: 'lightgray'},
      ];
     
}
