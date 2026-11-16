# Magellon tutorial video: narration

One video, four chapters. The text under each scene is spoken as written, one
sentence at a time; every on-screen action in record.py waits for the sentence it
belongs to, so the picture and the voice stay together. Lines in [brackets] say
what is on screen and are not spoken. Numbers and names are spelled the way the
voice should say them. Keep sentences short: one idea, one action.

---

## Chapter 1. Welcome

### Scene 1.1 Title card
[Title card.]

Welcome to Magellon. This tour shows you how to browse a session, import your own data, and look after accounts. There are three roles. Viewers can look at everything, Members can also import and process data, and Administrators can also manage accounts. Each chapter adds what is new for the next role.

---

## Chapter 2. For everyone: viewing a session

### Scene 2.1 Choosing a session
[Images page. Open the session drop-down and choose the tutorial session.]

Everything starts on the Images page. Choose a session from the list at the top left.

### Scene 2.2 The atlas and the columns
[The atlas. Then a grid square, a square, a hole and an exposure, one per column.]

At the top is the atlas, an overview of the whole grid. Below it, the session is laid out in columns, in the order the data was collected. Click a grid square, and its squares appear in the next column. Click a square to see its holes. Click a hole to see its exposures. Then click an exposure to open it on the right. In four clicks, you go from the whole grid to a single exposure.

In each column, images that have children come first. Images with nothing below them come last, out of your way.

### Scene 2.3 The other layouts
[The Grid, Tree and Table buttons in turn. Sort the table by resolution, open the best image, back to the columns.]

The buttons next to the session name show the same session in other ways. Grid shows every image as a thumbnail. Tree shows the session as folders you can open. Table lists every image with its values. Click a column heading to sort by it, here by resolution, so the best images come first. Click an image in any layout, and the columns follow it.

### Scene 2.4 Filtering: one condition
[Open the filter. The condition is CTF resolution, at most, 4. Show the hint and the count.]

The filter finds the images you care about. Click the filter button. A condition has three parts: a field, a comparison, and a value. Here the field is C-T-F resolution. The comparison is "at most". And the value is four. That reads like a sentence: C-T-F resolution is at most four angstroms.

Under the value, Magellon shows the range in this session, so you know what to type. And at the bottom, it counts the matching images before you apply anything.

You can filter on resolution, magnification, defocus, pixel size, the number of children, and the name.

### Scene 2.5 Filtering: combining conditions
[Add Magnification = 59000. Then a group set to OR, with NOT on: name contains 00034gr, magnification not 59000.]

You can combine conditions. Add a second one: magnification equals fifty-nine thousand. The switch at the top says how they combine. With "and", every condition must hold. With "or", any one is enough.

For mixed logic, add a group. A group works like brackets. Set this group to "or", and switch on "not", so it means: none of these. Inside, exclude grid square thirty-four, and anything not at fifty-nine thousand. The sentence at the bottom reads the whole filter back, so you can check it.

### Scene 2.6 Filtering: the result
[Apply. The chip. Grid and Table show the matches; the columns keep only the path to them; the tree too. Clear the chip.]

Apply the filter, and it appears as a chip under the toolbar. It works in every layout. Grid and Table show just the matching images. The columns also keep the grid squares and holes above each match, so you can still click down to it. Here, only one grid square leads to a good exposure. The tree works the same way. The server does all of this, so it stays fast even for very large sessions. Click the cross on the chip to clear the filter.

### Scene 2.7 Looking at an exposure
[An exposure. The Image, FFT, CTF, Frame Alignment and Metadata tabs.]

Click an exposure to open it. The header shows magnification, defocus, pixel size and dose. The Image tab shows the exposure. Scroll to zoom, and drag to look around. The F-F-T tab shows its Fourier transform. The C-T-F tab shows the defocus, the astigmatism, the resolution, and the fit plots. Frame Alignment shows the motion-corrected exposure from MotionCor.

Both tabs show the exact command that made the result, with a copy button. So you can always check the settings, or run it again yourself. Metadata lists every value the microscope recorded.

---

## Chapter 3. For Members: importing and processing

### Scene 3.1 The import page
[The Import page and its four tabs.]

Members can do everything we have seen, and three more things: import sessions, test settings on a single file, and pick particles. Open Import from the menu. There is a tab for each kind of data. We will import a Leginon session.

### Scene 3.2 Filling in the form
[Type 24dec03a; the frames folder and gain file fill in, and a note says the images folder wasn't found. Point at the gain file and its Browse button. Type the images path. Change the custom name to 24dec03a_tour. Point at the two copy options.]

Type the Leginon session name, twenty-four dec oh three a. It must be exactly the name the session has in Leginon, because Magellon reads the images and their settings from the Leginon database by this name. Magellon then looks for the session's files in the lab's leginondata and framesdata folders, and fills in what it finds. Here it found the frames folder and the gain file. If there is more than one gain file, Magellon takes the first one it finds, so check it. To use another one, click Browse and choose it. It could not find the images folder, so it says so. Type that path in, or click Browse to pick the folder. Use Browse in the same way whenever your files are somewhere else. Magellon only reads these folders. It never changes them.

The custom name is the session's name in Magellon. The Leginon name is already taken, and the form tells you who owns it. So give it a new name.

The two copy options are only for exporting the session to another site. With them, the images and the movies are copied into the session, so the import takes much longer and uses more space. For normal work, leave them off.

### Scene 3.3 Starting the import
[Click Import. The progress window.]

Click Import. The progress window shows each stage, how many images are done, and the time left. Up to four imports run at once. Any others wait in a queue, and take turns fairly.

### Scene 3.4 Working while it runs
[Run in background. The chip in the top bar. The Jobs panel.]

Click Run in background to keep working. A chip in the top bar keeps showing the progress. The Jobs panel lists everything running in the lab. A session of three hundred images takes about an hour.

### Scene 3.5 An hour later
[Jobs panel: Done. Open the session, an exposure, its CTF tab.]

An hour later, the import shows Done. Done means every exposure has its motion correction and C-T-F results. The session is ready to browse.

### Scene 3.6 Testing a single file
[Run Processing Jobs. Upload a movie and its gain file. Set the pixel size. Run. The result appears below. Then CTF Estimation: upload a micrograph, run, the result appears below.]

To test settings on one file, open Run Processing Jobs from the menu. Upload a movie, and its gain file. Open the advanced parameters, and set the real pixel size for your data. Run it. Tests go ahead of imports, so the result comes back quickly. It appears right below the form, with the command that was run.

You can test C-T-F estimation the same way. Choose C-T-F estimation as the pipeline, and upload a micrograph. Run it, and the result shows the defocus, the resolution, and the fit plots. Nothing is saved, so download what you want to keep.

### Scene 3.7 Picking particles by hand
[Particle Picking tab. A new record. The add tool: picks on the image; the counts on the left; the radius slider; remove and undo; Help; save.]

In your own sessions, you can pick particles, by hand or automatically. Open an exposure, and its Particle Picking tab. Picks are kept in picking records, so each way of picking can have its own record, and you can compare them. Start a new record for your hand picks.

Choose the add tool, and click on each particle. The counts on the left show how many picks you have, and the coloured classes let you mark picks as good, edge, contamination, or uncertain. The slider sets the size of the circle, the particle radius. To take a pick back, use the remove tool, or undo. Press H to see all the shortcuts, and save your picks with control S.

### Scene 3.7b Automatic picking with Topaz
[The settings: Algorithm Settings, Topaz. Its settings. Preview and tune: the count, the score map, the threshold, Accept.]

For automatic picking, open the settings. At the top, you choose the picking method. There are two: Topaz, and the template picker. Topaz finds particles with a trained neural network, so it needs no templates. Its settings are below: the model, the score threshold, the exclusion radius, and the scale. If you have picked some particles by hand, Train session can teach Topaz from your own picks.

Click Preview and tune. Magellon runs Topaz on this image, without saving anything. The preview shows how many particles it found, and a map of where it found them. Move the score threshold to keep more or fewer picks, and run it again to see the difference. When the picks look right, accept them, and they are saved as a new record. Save current image does the same in one step, without the preview.

### Scene 3.7c The template picker
[Choose Template Picker. Its settings: diameter, threshold, maximum picks, pixel sizes. Back to Topaz.]

The template picker works another way. It looks for particles that match template images of your particle. You set the particle diameter, the threshold, the most picks to keep, and the pixel sizes of your images and your templates. It runs the same way: preview and tune, then save.

### Scene 3.7d Batch picking
[Run batch: the dialog. Magnification, tolerance, record name, the list. Select none, tick three, Launch. Progress, picks per image. The Jobs panel.]

To pick many images at once, click Run batch. Magellon lists the session's images at one magnification, here every exposure at fifty-nine thousand. The tolerance widens that match, and the name is the record the picks are saved in. You can run all of them, or only some. Here I choose three. Launch it, and each image is picked with the current settings. The window shows the progress, and how many particles each image gave. A batch also appears in the Jobs panel, so you can close this window and keep working.

### Scene 3.7e Comparing records
[The records list: the hand picks, the Topaz record, the batch record. Switch between them. The record menu: Export as COCO.]

Every run is kept as its own record. Choose a record from the list, and its picks appear on the image. Switch between them to compare your hand picks with Topaz. From the record menu, you can also export the picks, for example in COCO format.

### Scene 3.8 Stopping an import
[A second import running. Jobs panel, red stop button, confirmation, Stop and delete.]

To stop an import, use the red stop button in the Jobs panel. Stopping does not pause it. It deletes everything the import has made so far. Your original data is not touched, so you can import again. Magellon asks you to confirm.

### Scene 3.9 Exporting and deleting
[The Export page. Then the session epu_deletedemo: bin icon, type the name, Delete, the notification.]

The Export page writes a RELION star file for a session.

When you no longer need a session, delete it, because storage is shared by the whole lab. Choose the session, and click the bin icon. Type its name to confirm. The Delete button stays grey until the name matches. Deleting is permanent, but your original data stays, so you could import it again.

---

## Chapter 4. For administrators

### Scene 4.1 Accounts
[Security page, User Management, Add User.]

Administrators can do everything a Member can, in every session. They also manage accounts, on the Security page. To add someone, click Add User, and enter a name and a first password.

### Scene 4.2 Roles
[The roles dialog. Then the deactivate and reset password icons.]

Then give them a role. Most people are Members. The change applies straight away. The icons on each row also deactivate an account, or reset a password.

### Scene 4.3 Checking access
[Permission Checker, then Session Access.]

The Permission Checker shows what a person is allowed to do. Session Access shares one session with one person, such as a collaborator.

### Scene 4.4 Processing services
[Plugins, then Pipeline Health.]

The Plugins page shows each processing service, and whether it is running. Pipeline Health shows the queues behind them. If imports seem stuck, look here first.

### Scene 4.5 Closing
[A session open on the Images page.]

That is Magellon. The written user guide covers every detail. Thanks for watching.
