mae = np.mean(abs_errors)

mse = np.mean(errors ** 2)

rmse = np.sqrt(mse)

non_zero = actual != 0
if non_zero.sum() > 0:
    mape = np.mean(np.abs(errors[non_zero] / actual[non_zero])) * 100
else:
    mape = 0.0

ss_res = np.sum(errors ** 2)
ss_tot = np.sum((actual - np.mean(actual)) ** 2)
r2 = 1 - (ss_res / (ss_tot + 1e-8))

actual_direction = np.diff(actual) > 0
predicted_direction = np.diff(predicted) > 0
direction_accuracy = np.mean(actual_direction == predicted_direction) * 100

if np.std(strategy_returns) > 1e-8:
    sharpe_ratio = (np.mean(strategy_returns) / np.std(strategy_returns)) * np.sqrt(252)
else:
    sharpe_ratio = 0.0