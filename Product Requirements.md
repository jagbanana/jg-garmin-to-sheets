# **Garmin Data Sync Tool \- Requirements Document**

## **Overview**

A Python command-line tool, packaged as a Docker container (optional), that pulls daily health metrics from Garmin Connect and stores them in Google Sheets.

App Name: JGGarminSync

## **Phase 1 Scope**

* Command-line interface  
* Docker containerization as an option with direct running via Python as the main option 
* Manual execution (no scheduling)  
* Support for date range queries  
* Focus on daily metrics

## **Functional Requirements**

### **Data Collection**

1. Must authenticate with Garmin Connect  
2. Must pull the following daily metrics (note some values may be blank for a given day, which is okay):  
   * Sleep Score  
   * Sleep Length  
   * Weight  
   * Body Fat Percentage  
   * Blood Pressure (Systolic/Diastolic)  
   * Daily Active Calories  
   * Daily Resting Calories  
   * Resting Heart Rate  
   * Average Stress  
   * VO2 Max Running   
   * VO2 Max Cycling  
   * Daily Intensity Minutes  
   * Daily All Activity Count  
   * Running Activity Count  
   * Running Distance  
   * Cycling Activity Count  
   * Cycling Distance  
   * Strength Activity Count  
   * Strength Training Duration  
   * Cardio Activity Count  
   * Cardio Training Duration

### **User Interface**

1. Command-line arguments must include:  
   * Start date  
   * End date  
   * Garmin credentials
   * Google Sheets target information
2. Must provide clear feedback on:  
   * Authentication status  
   * Data retrieval progress  
   * Success/failure of data storage  
   * Any errors encountered

### **Data Storage**

1. Must authenticate with Google Sheets API  
2. Must update specified Google Sheet with retrieved data  
3. Must maintain existing sheet formatting/structure  
4. Must not overwrite existing data without user confirmation

## **Technical Requirements**

### **Docker Configuration**

1. Must use Python 3.9+ base image  
2. Must include all necessary dependencies  
3. Must handle secrets securely (environment variables)  
4. Must include appropriate logging  
5. Must provide clear build and run instructions

### **Error Handling**

1. Must gracefully handle:  
   * Authentication failures  
   * Network connectivity issues  
   * Missing or invalid data  
   * API rate limiting  
   * Google Sheets API errors  
2. Must provide meaningful error messages  
3. Must log errors appropriately

### **Security**

1. Must securely handle credentials  
2. Must not store credentials in container or code  
3. Must use appropriate API security practices  
4. Must validate input data

## **Non-Functional Requirements**

### **Performance**

1. Should complete data pull and storage for a single day within 30 seconds  
2. Should handle up to 365 days of data in a single request

### **Reliability**

1. Should handle Garmin Connect API timeouts and retry appropriately  
2. Should validate data before storage

### **Maintainability**

1. Must include documentation:  
   * Setup instructions  
   * Usage examples  
   * Environment variable requirements  
   * Troubleshooting guide  
2. Must follow Python best practices and include comments  
3. Must use type hints for better code maintainability

## **Future Considerations**

The following are out of scope for Phase 1 but should be considered in the design:

1. Scheduling capability  
2. Web interface integration with WordPress  
3. Cloud deployment to Google Cloud Run  
4. Data validation and cleaning features  
5. Data analysis and visualization  
6. Multiple user support

## **Phase 2 Scope**

* Make the code available on GitHub for others to use  
* Improve the user interface and initial configuration, while keeping it text-based for now  
* Remove any security items that are specific for me so I don’t put personal data up on GitHub accidentally

### Requirements

1. Documentation and Setup  
   1. Add a detailed README.md with clear setup instructions, including:  
      1. Required API credentials and how to obtain them  
      2. Environment variables configuration  
      3. Docker setup steps  
      4. Example usage with sample commands  
   2. Add a license file (LICENSE.md)  
2. Security Enhancements  
   1. Move all credentials to environment variables  
   2. Create a template .env file (.env.example) with dummy values  
   3. Add .env to .gitignore  
   4. Remove any hardcoded paths or IDs  
   5. Document security best practices for users

## **Phase 3 Scope**

* Simple desktop version for non-technical users, supporting Windows. The goal is to have something people can download and use without configuration. On running, they could enter their Garmin credentials, enter a start and end date for the report, hit run, and then have a CSV or XLSX generated (if XLSX is complicated, CSV is fine).  
* Instead of outputting to Google Sheets (which is where most of the setup complexity comes from), the tool can output to a CSV file or even XLSX locally. Users could then copy the data out of there and paste it wherever they want.

### User Interface Requirements

* Simple, intuitive window layout following Windows design guidelines  
* Clear input validation and error messages  
* Progress indicator during data fetch  
* Ability to select date range via calendar control  
* Clear success/failure notifications  
* Optional "Save As" dialog for output file location (default to Documents folder)  
* Dark theme matching provided style guide (\#1a1a1a background, \#2a2a2a panels, etc.)  
* The frontend user interface should be in an HTML/CSS/JS type stack using Electron \+ Python backend.

### Security Requirements

* Secure handling of Garmin credentials  
* Optional encrypted credential storage with 30-day expiration  
* Clear privacy policy about data handling  
* No data transmission except to Garmin's servers

### Output Requirements

* CSV output with proper escaping and UTF-8 encoding  
* Consistent date formatting  
* Column headers matching Garmin's terminology  
* Handling of missing data points  
* File naming convention (e.g., "garmin\_export\_YYYY-MM-DD\_to\_YYYY-MM-DD.csv")  
* Default save location in user's Documents folder

### Error Handling

* Graceful handling of network issues  
* Clear error messages for authentication failures  
* Ability to retry failed operations  
* Validation of date ranges before fetching  
* Disk space checking before writing files  
* Specific handling for expired stored credentials

### Performance Requirements

* Response time under 2 seconds for UI interactions  
* Progress updates during longer operations  
* Minimal memory footprint  
* Efficient handling of large date ranges

## **Phase 4 Scope**

* Cloud deployment to Google Cloud Run  
* Web interface integration with WordPress  
* Multiple user support

For Phase 2, the container should run on Google Cloud and be accessible on the internet. For users to interact, I’d like a WordPress frontend.

The frontend user interface does not need to remember information for now (meaning nothing needs to be stored in the WordPress database for return visits). It should just have input fields, run, and then provide feedback (if the run was successful or had an issue).

The input fields would include:

* Garmin email  
* Garmin password  
* Google Sheet ID  
* Date range start  
* Date range end

For the Google Sheet connection, I imagine there needs to be a Google Account authorization that happens.

The Garmin email and password (and any other secure information) should be sent securely so that the app doesn’t put any account information at risk.