import {FileUpload} from './components/FileUpload';
import Navbar from './components/Navbar';
import { Helmet } from 'react-helmet';
function App() {
  return (
    <div className="App">
      <Helmet>
        <title>2D Classifier</title>
        <meta 
          name="description" 
          content="2D Classifier is a machine learning application where users can interact with a pre-trained model, modify outputs, and retrain it to improve accuracy. " 
        />

        <meta property="og:title" content="2D Classifier - Improve Machine Learning Models with User Interaction" />
        <meta property="og:description" content="Users can get outputs from a pre-trained model, modify results, and retrain the model to enhance performance." />
      </Helmet>
      <Navbar />
      <div style={{paddingTop:"20px"}}><FileUpload /></div>
    </div>
  );
}

export default App;
