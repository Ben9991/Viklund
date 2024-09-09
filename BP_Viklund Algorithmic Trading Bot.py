#region imports
from AlgorithmImports import *
#endregion
import decimal as d
from datetime import timedelta
import numpy as np
from AlgorithmImports import *
from System.Drawing import Color

class MovingAverageCrossAlgorithm(QCAlgorithm):

    def Initialize(self):
        '''Initialise the data and resolution required, as well as the cash and start-end dates for your algorithm. All algorithms must initialized.'''

        self.SetStartDate(2022, 5, 1) #Startdate
        self.SetEndDate(2023, 9, 1) #Enddate
        self.SetCash(100000)             #Set Strategy Cash
        self.signals = self.get_text() #Call Bulk Data Download from drop box of signals

        self.bp = self.AddEquity("BP", Resolution.Daily, Market.USA).Symbol #Add Seclected Security

        self.bnd = self.AddEquity("BND", Resolution.Daily, Market.USA).Symbol

    
 
        self.earnings_call_period = False
        self.earnings_period_end_date = None
        self.viklund_control = False
        self.prev_quarter = None
        self.prev_year = None

        self.SetBenchmark("QEFA") #A NASDAQ ETF that tracks companies with shares in the NASDAQ including BP Plc


        # create a 5 day exponential moving average
        self.fast = self.EMA(self.bp, 5, 0.3)

        # create a 30 day exponential moving average
        self.slow = self.EMA(self.bp, 30, 0.8)

        self.previous = None
        self.tolerance = 0.015 #Risk Management
    
        self.SetWarmUp(timedelta(days=20))
        # Create a Chart object with the title "Data Chart"
        stockPlot = Chart("Data Chart")

        # Add a series named "Buy" to the chart with Scatter plot type, using "$" as the y-axis label,
        # blue color, and Triangle marker symbol.
        stockPlot.AddSeries(Series("Buy", SeriesType.Scatter, "$", Color.Blue, ScatterMarkerSymbol.Triangle))

        # Add a series named "Sell" to the chart with Scatter plot type, using "$" as the y-axis label,
        # red color, and TriangleDown marker symbol.
        stockPlot.AddSeries(Series("Sell", SeriesType.Scatter, "$", Color.Red, ScatterMarkerSymbol.TriangleDown))

        # Add a series named "Short" to the chart with Scatter plot type, using "$" as the y-axis label,
        # orange color, and TriangleDown marker symbol.
        stockPlot.AddSeries(Series("Short", SeriesType.Scatter, "$", Color.Orange, ScatterMarkerSymbol.TriangleDown))

        # Add a series named "V-Buy" to the chart with Scatter plot type, using "$" as the y-axis label,
        # purple color, and TriangleDown marker symbol.
        stockPlot.AddSeries(Series("V-Buy", SeriesType.Scatter, "$", Color.Purple, ScatterMarkerSymbol.TriangleDown))

        # Add a series named "V-Sell" to the chart with Scatter plot type, using "$" as the y-axis label,
        # yellow color, and TriangleDown marker symbol.
        stockPlot.AddSeries(Series("V-Sell", SeriesType.Scatter, "$", Color.Yellow, ScatterMarkerSymbol.TriangleDown))

        # Add the created stockPlot chart to some container or plot area (not shown in this snippet).
        self.AddChart(stockPlot)

    def OnData(self, data):
        # self.signals["score"]
        system_datetime = self.Time + timedelta(hours=8)
        check_date = self.signals.loc[self.signals['date'] <= system_datetime]
        matching_indices = check_date.index.tolist() 
        if matching_indices:
            self.Log('Match_ind not empty')
            row_num = matching_indices[-1]
            if self.prev_quarter is None or self.prev_year is None:
                self.Log('Quarter is None')
                self.prev_quarter = self.signals['quarter'][row_num]
                self.prev_year = self.signals['date'][row_num].year
                self.earnings_call_period = True
                self.Log('Set prev quarter variable')

            elif self.prev_quarter and self.prev_year is not None:
                if self.prev_quarter == self.signals['quarter'][row_num]\
                    and self.prev_year == self.signals['date'][row_num].year:
                    self.earnings_call_period = False
                else:
                    self.prev_quarter = self.signals['quarter'][row_num]
                    self.prev_year = self.signals['date'][row_num].year
                    self.earnings_call_period = True
                    self.Log('New Quarter')


            
            # year_obj = datetime.strptime(year, '%Y-%m-%d %H:%M:%S').year
            # self.Log(date_1.year)
            # self.earnings_call_period = True

        else:
            self.earnings_call_period = False
            



        # wait for our slow ema to fully initialize
        if self.IsWarmingUp: return

        # This prevents us from trading more than once per day
        if self.previous is not None and self.previous.date() == self.Time.date():
            return

        #Plotting the lines for evaluation purposes
        self.Plot("Data Chart", "ema-fast", self.fast.Current.Value)
        self.Plot("Data Chart", "ema-slow", self.slow.Current.Value)
        self.Plot("Data Chart", self.bp, self.Securities[self.bp].Close)
        self.Plot("Data Chart", self.bnd, self.Securities[self.bnd].Close)

      
        self.Log(self.fast)




        
        

        # I dentify earnings period 
        if self.earnings_period_end_date is not None:
            #Seeking the closest quarterly earnings call signal and liquidating all current positions if this item is found
            if self.earnings_period_end_date <= self.Time:
                self.Liquidate()
                self.Log('Liquidated')
                self.Plot("Data Chart", "V-Sell", self.Securities[self.bp].Price)
                self.Log(f'end-triggered: {self.earnings_period_end_date}')
                self.viklund_control = False
                self.earnings_call_period = False
                self.earnings_period_end_date = None

        # Defining core trading strategy EMA cross
        if self.earnings_call_period == False:
            # Ensuring we are not still within the long, or short buffer period set by the NN Execution component
            if not self.viklund_control:
                # Enter a long position if our holdings are allocated to a short position, or if we do not have any holding at all
                if self.Portfolio["BP"].Quantity <= 0:
                    # If EMA-Fast is greater than EMA-Slow then we may have identified the lowest low and wish to go long 
                    if self.fast.Current.Value > self.slow.Current.Value * (1 + self.tolerance ):
                        self.SetHoldings("BP", 0.8)
                        self.SetHoldings("BND", -0.2)
                        self.Plot('Data Chart', "Buy", self.Securities[self.bp].Price)

                # If we are already long and EMA-Fast is lower then EMA-Slow, then we want to liquidate all current positions in order to safegaurd our potential earnings from loss
                # Tolerance is factored in
                if self.Portfolio["BP"].Quantity > 0 and (self.fast.Current.Value * (1 + self.tolerance )) < self.slow.Current.Value:
                    self.Liquidate()
                    self.Plot("Data Chart", "Sell", self.Securities[self.bp].Price)


        # Triggering Viklan NN to take over trading decisions
        elif self.earnings_call_period == True:
            
            self.Log('Earnings Call Period = True')

            # Locate the signal score from  the provided data dump csv content        
            signal = self.signals["score"][row_num]
            signal = float(signal)

            #If the signal is greater than our certainty threshold then we go long
            if signal > 0.2:
                self.Log(signal)
                # Set the buffer period 30 days in the future. No trading will take place until then
                self.earnings_period_end_date = self.Time + timedelta(days=30)
                # Set Viklund control flag to true to prevent core trading strategy, EMA cross, from taking over
                self.viklund_control = True
                # Position sizing based off NN signal, 80% if our cash into BP the remaining allocated towards BNDs
                self.SetHoldings("BP", 0.8)
                self.SetHoldings("BND", -0.2)
                self.Log('Buy')
                # Plot the price at which this buy order was placed
                self.Plot("Data Chart", "V-Buy", self.Securities[self.bp].Price)
            
            #If the signal is less than our certainty threshold then we go short
            elif signal < -0.2:
                # Set the buffer period to roughly 6 days in the future. No trading will take place until then
                self.earnings_period_end_date = self.Time + timedelta(days=(0.2 * 30))
                 # Set Viklund control flag to true to prevent core trading strategy, EMA cross, from taking over
                self.viklund_control = True
                # Position sizing based off NN signal, 80% if our cash into shorting BP, the remaining allocated towards BNDs
                self.SetHoldings("BP", -0.8)
                self.SetHoldings("BND", 0.2)
                self.Log('Short')
                # Plot the price at which this short order was placed
                self.Plot("Data Chart", "Short", self.Securities[self.bp].Price)
            # Plot the price at which this short order was placed  
            # Do nothing if threshold is not reached, revert back to core trading strategy  
            elif signal > -0.2 and signal < 0.2:
                self.viklund_control = False
                self.earnings_call_period = False

        #Update previous time to current time after first trade of the day has been made    
        self.previous = self.Time


    def get_text(self):
        # import custom data
        # Note: dl must be 1, or it will not download automatically
        # 'https://www.dropbox.com/scl/fi/b6ixmavoqgts8jgvhi9va/viklund_sent_signals.csv?rlkey=8c9wxyaiij1rz09g1cavgmc8p&dl=1'
        url = 'https://www.dropbox.com/scl/fi/n7f47t5bmnf26cwva1kjr/bp_Viklund_Sentiment_signals.csv?rlkey=0yi9oxt2fz3ito8eg2cuxezye&st=1p73raa0&dl=1'
        data = self.Download(url).split('\n')
        
        
        
        date_ = []
        sentiment_ = []
        score_ = []
        sentiment_id = []
        quarter = []

        for i in range(1,len(data)-1):
            # Date time split
            proce_date = datetime.strptime(data[i].split(',')[0], '%Y-%m-%dT%H:%M:%S%z').replace(tzinfo=None)
            # Fill arrays with respective data
            date_.append(proce_date)
            sentiment_.append(data[i].split(',')[1])
            score_.append(data[i].split(',')[2])
            sentiment_id.append(data[i].split(',')[3])
            quarter.append(data[i].split(',')[4])

    
        # create a pd dataframe with 1st col being date and 2nd col being headline (content of the text)
        df = pd.DataFrame({
            "date" : date_, 
            "setiment" : sentiment_,
            "score": score_, 
            "sentiment_id":sentiment_id, 
            "quarter": quarter})
        # Return dataset    
        return df

        