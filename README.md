# Fluorometer Acquisition App

This application was written to communicate, acquire, display and save data produced by a Sens-Tech P25USB photodetector. Measurement of Ammonium in seawater reacted with OPA was the use case for this detector, detecting absorbance at 460nm. 

Application is written in PyQt5, utilising PyQtGraph for the charting and display of acquired data. The pyserial package was utilised to communicate with the detector, information on the detector can be found [here](http://www.sens-tech.com/index.php/p25-usb-module).



Features:

- Simplistic interface, no learning curve
- Writing of data to disk each time - no lost data!
- Performant charting, low computer usage
- Configure key detector settings to optimise for setup



Future integrations:

- Use platform to create generic serial communication app
- Incorporate different charting types or customisation



 

