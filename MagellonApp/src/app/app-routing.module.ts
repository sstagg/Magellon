import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { ViewImagesComponent } from './view-images/view-images.component';


const routes: Routes = [
  {path: 'view-image', component: ViewImagesComponent}
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule]
})
export class AppRoutingModule { }
