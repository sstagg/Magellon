from skimage import data
import napari

viewer = napari.view_image(data.astronaut(), rgb=True)
napari.run()  # start the event loop and show viewer