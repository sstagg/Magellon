import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { FileUpload } from './components/FileUpload'; 
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import Terms from './pages/Terms';
import { Helmet } from 'react-helmet';

function App() {
  return (
    <Router>
      <div
        className="App"
        style={{
          display: 'flex',
          flexDirection: 'column',
          minHeight: '100vh',
        }}
      >
        <Helmet>
          <title>Cryosift</title>
          <meta 
            name="description" 
            content="2D Classifier is a machine learning application where users can interact with a pre-trained model, modify outputs, and retrain it to improve accuracy." 
          />
          <meta property="og:title" content="2D Classifier - Improve Machine Learning Models with User Interaction" />
          <meta property="og:description" content="Users can get outputs from a pre-trained model, modify results, and retrain the model to enhance performance." />
        </Helmet>

        <Navbar />

        {/* Main content takes remaining space */}
        <div style={{ flex: 1 }}>
          <Routes>
            <Route path="/" element={<div style={{paddingTop:"20px"}}><FileUpload /></div>} />
            <Route path="/terms" element={<Terms />} />
          </Routes>
        </div>

        <Footer />
      </div>
    </Router>
  );
}

export default App;
