import './App.css';
import FileUpload from './components/FileUpload';
import Navbar from './components/Navbar';

function App() {
  return (
    <div className="App">
      <Navbar />
      <div style={{paddingTop:"20px"}}><FileUpload /></div>
    </div>
  );
}

export default App;
