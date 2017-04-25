import codecs
import numpy as np
import cPickle
import sqlite3
from geopy.distance import great_circle
from keras.engine import Merge
from keras.layers import Embedding, LSTM, Dense, Dropout
from keras.models import Sequential
from preprocessing import pad_list, construct_1D_grid, get_coordinates, print_stats, index_to_coord

# import matplotlib.pyplot as plt

print(u'Loading training data...')
X_L, X_R, X_E, X_T, N, C = [], [], [], [], [], []
UNKNOWN, PADDING = u"<unknown>", u"0.0"
dimension, input_length = 50, 50
vocabulary = cPickle.load(open("./data/vocabulary.pkl"))

training_file = codecs.open("./data/eval_lgl.txt", "r", encoding="utf-8")
for line in training_file:
    line = line.strip().split("\t")
    C.append((float(line[0]), float(line[1])))
    X_L.append(pad_list(input_length, eval(line[2].lower()), True))
    X_R.append(pad_list(input_length, eval(line[3].lower()), False))
    X_E.append(construct_1D_grid(eval(line[4]), True))
    X_T.append(construct_1D_grid(eval(line[5]), False))
    N.append(line[6])

print(u"Vocabulary Size:", len(vocabulary))
print(u'Loaded', len(C), u'test examples.')
#  --------------------------------------------------------------------------------------------------------------------
print(u'Preparing vectors...')
word_to_index = dict([(w, i) for i, w in enumerate(vocabulary)])

for x_l, x_r in zip(X_L, X_R):
    for i, w in enumerate(x_l):
        if w in word_to_index:
            x_l[i] = word_to_index[w]
        else:
            x_l[i] = word_to_index[UNKNOWN]
    for i, w in enumerate(x_r):
        if w in word_to_index:
            x_r[i] = word_to_index[w]
        else:
            x_r[i] = word_to_index[UNKNOWN]

X_L = np.asarray(X_L)
X_R = np.asarray(X_R)
X_E = np.asarray(X_E)
X_T = np.asarray(X_T)

#  --------------------------------------------------------------------------------------------------------------------
print(u'Building model...')
model_left = Sequential()
model_left.add(Embedding(len(vocabulary), dimension, input_length=input_length))
model_left.add(LSTM(output_dim=50))
model_left.add(Dropout(0.2))

model_right = Sequential()
model_right.add(Embedding(len(vocabulary), dimension, input_length=input_length))
model_right.add(LSTM(output_dim=50, go_backwards=True))
model_right.add(Dropout(0.2))

model_target = Sequential()
model_target.add(Dense(output_dim=100, activation='relu', input_dim=36*72))
model_target.add(Dropout(0.2))
model_target.add(Dense(output_dim=50, activation='relu'))

model_entities = Sequential()
model_entities.add(Dense(output_dim=100, activation='relu', input_dim=36*72))
model_entities.add(Dropout(0.2))
model_entities.add(Dense(output_dim=50, activation='relu'))

merged_model = Sequential()
merged_model.add(Merge([model_left, model_right, model_target, model_entities], mode='concat', concat_axis=1))
merged_model.add(Dense(25))
merged_model.add(Dense(36*72, activation='softmax'))
merged_model.load_weights("./data/lstm.weights")
merged_model.compile(loss='categorical_crossentropy', optimizer='adam', metrics=['accuracy'])

print(u'Finished building model...')
#  --------------------------------------------------------------------------------------------------------------------
conn = sqlite3.connect('./data/geonames.db')
choice, prediction = [], []
for p, c, n in zip(merged_model.predict([X_L, X_R, X_T, X_E]), C, N):
    p = index_to_coord(np.argmax(p))
    candidates = eval(get_coordinates(conn.cursor(), n))
    if len(candidates) == 0:
        print(u"Don't have an entry for", n, u"in GeoNames")
        continue
    temp = []
    for candidate in candidates:
        temp.append((great_circle(p, (float(candidate[0]), float(candidate[1]))).kilometers, (float(candidate[0]), float(candidate[1]))))
    best = sorted(temp, key=lambda (x, y): x)[0]
    choice.append(great_circle(best[1], c).kilometers)
    prediction.append(great_circle(p, c).kilometers)
    print(n, p, c, choice[-1])
    print(candidates, sorted(temp)[0])
    print("-----------------------------------------------------------------------------------------------------------")

print(u"Median error for choice:", np.log(np.median(choice)))
print(u"Mean error for choice:", np.log(np.mean(choice)))
print_stats(choice)
print(u"Median error for prediction:", np.log(np.median(prediction)))
print(u"Mean error for prediction:", np.log(np.mean(prediction)))
print_stats(prediction)

# plt.plot(range(len(choice)), sorted(choice))
# plt.plot(range(len(prediction)), sorted(prediction))
# plt.xlabel(u"Examples")
# plt.ylabel(u'Error')
# plt.show()
