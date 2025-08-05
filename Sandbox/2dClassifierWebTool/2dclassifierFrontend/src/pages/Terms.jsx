import React from 'react';
import { Box, Typography } from '@mui/material';

const Terms = () => {
  return (
    <Box sx={{ p: 4, maxWidth: 900, margin: 'auto' }}>
      <Typography variant="h4" gutterBottom>Terms of Use</Typography>
      <Typography variant="subtitle2" gutterBottom>Effective Date: 7/28/2025</Typography>

      <Typography paragraph>
        By accessing or using our website and associated analysis tools, you (“you” or “User”) agree to these Terms of Use.
      </Typography>

      <Typography variant="h6" gutterBottom>1. Use of the Service</Typography>
      <Typography paragraph>
        We provide an online platform where users may upload cryo-electron microscopy (cryo-EM) class averages and associated metadata files for analysis. 
        This service is available to both non-commercial and commercial users. Use of the site is open to all individuals and institutions. 
        We reserve the right to modify, suspend, or discontinue the site or services at any time without notice.
      </Typography>

      <Typography variant="h6" gutterBottom>2. User Responsibilities</Typography>
      <Typography paragraph>
        You are solely responsible for the content you upload. By submitting files, you affirm that you have the necessary rights and permissions to use and share those files. 
        You agree not to upload any data that is:
      </Typography>
      <ul>
        <li>Proprietary or confidential without authorization,</li>
        <li>In violation of applicable laws or regulations,</li>
        <li>Malicious, including viruses or harmful code.</li>
      </ul>

      <Typography variant="h6" gutterBottom>3. No Warranty</Typography>
      <Typography paragraph>
        The service is provided "as is" and “as available” without warranties of any kind, express or implied. 
        We do not guarantee the accuracy, reliability, or completeness of analysis results. 
        Users should independently verify any conclusions drawn from use of the tool.
      </Typography>

      <Typography variant="h6" gutterBottom>4. Limitation of Liability</Typography>
      <Typography paragraph>
        To the fullest extent permitted by law, we are not liable for any direct, indirect, incidental, or consequential damages arising from use of this website or its services, 
        including but not limited to data loss or misinterpretation of analysis results.
      </Typography>

      <Typography variant="h6" gutterBottom>5. Intellectual Property</Typography>
      <Typography paragraph>
        You retain all rights to the data you upload. By using the site, you grant us a limited, non-exclusive right to process and analyze the uploaded data solely 
        for the purpose of providing the requested service.
      </Typography>

      <Typography variant="h6" gutterBottom>6. Changes to the Terms</Typography>
      <Typography paragraph>
        We may update these Terms of Use from time to time. Continued use of the site after any changes constitutes acceptance of the revised terms.
      </Typography>

      <Typography variant="h6" gutterBottom>7. Contact</Typography>
      <Typography paragraph>
        For questions regarding these Terms of Use, please contact us at <a href="https://magellon.org/groups" target="_blank" rel="noopener noreferrer">magellon.org</a>
      </Typography>

      <Box mt={6}>
        <Typography variant="h4" gutterBottom>Privacy Policy</Typography>
        <Typography variant="subtitle2" gutterBottom>Effective Date: 7/28/2025</Typography>
        
        <Typography variant="h6" gutterBottom>1. No Personal Data Collected</Typography>
        <Typography paragraph>
          We do not collect or require personal identifying information such as names, email addresses, or user accounts to use our services.
        </Typography>

        <Typography variant="h6" gutterBottom>2. Uploaded Data</Typography>
        <Typography paragraph>
          Users may upload cryo-EM class averages, metadata files, or similar scientific data for analysis. By uploading data, you agree to the following:
        </Typography>
        <ul>
          <li>Uploaded files are used only for performing the requested computational analysis and improving the quality and performance of our tools.</li>
          <li>Uploaded files and results may be temporarily stored on our servers to facilitate processing. We do not guarantee long-term storage, and files may be deleted periodically without notice.</li>
          <li>We may review uploaded data internally for benchmarking, debugging, or to improve the service, but we do not share user-submitted data with third parties.</li>
        </ul>

        <Typography variant="h6" gutterBottom>3. Cookies and Tracking</Typography>
        <Typography paragraph>
          We do not use cookies, trackers, or analytics services that collect personally identifying information.
        </Typography>

        <Typography variant="h6" gutterBottom>4. Third-Party Services</Typography>
        <Typography paragraph>
          Our service does not rely on or transmit data to external third-party services. All processing is conducted within our internal infrastructure.
        </Typography>

        <Typography variant="h6" gutterBottom>5. Data Security</Typography>
        <Typography paragraph>
          We take reasonable measures to protect uploaded data from unauthorized access or disclosure. 
          However, we cannot guarantee absolute security, and users should avoid uploading sensitive or confidential information unless necessary.
        </Typography>

        <Typography variant="h6" gutterBottom>6. Changes to this Policy</Typography>
        <Typography paragraph>
          We may update this Privacy Policy from time to time. Continued use of the website constitutes acceptance of the updated policy.
        </Typography>

        <Typography variant="h6" gutterBottom>7. Contact</Typography>
        <Typography paragraph>
          If you have questions about this Privacy Policy or how your data is handled, please contact us at: <a href="https://magellon.org/groups" target="_blank" rel="noopener noreferrer">magellon.org</a>
        </Typography>
      </Box>
    </Box>
  );
};

export default Terms;
