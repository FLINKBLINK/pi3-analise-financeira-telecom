idades = [18, 22, 30, 45, 60]


import numpy as np
np_array = np.array([18, 22, 30, 45, 60])

notas = {'A': 'Alta', 'B': 'Baixa'} 
print(notas['A'])  # Saída: Alta


categorias = set(['A', 'B', 'A', 'C']) 
print(categorias)  # Saída: {'A', 'B', 'C'}

import pandas as pd 
#df = pd.read_csv('dados.csv')




# Busca lenta em lista
"SP" in ["SP", "RJ", "MG", "BA"]  # Tempo linear

# Busca rápida em set ou dict
"SP" in {"SP", "RJ", "MG", "BA"}    # Tempo constante

frutas = ["maçã", "banana", "laranja"]

print(frutas[1])  # banana

idade = {"Ana": 25, "Bruno": 30} 
print(idade["Ana"])  # 25


numeros = [1, 2, 2, 3] 
print(set(numeros))  # {1, 2, 3}

# Exemplo de Bubble Sort em Python 
def bubble_sort(lista): 
    n = len(lista) 
    for i in range(n): 
        for j in range(0, n - i - 1): 
            if lista[j] > lista[j + 1]: 
                lista[j], lista[j + 1] = lista[j + 1], lista[j] 
    return lista 
 
valores = [5, 2, 9, 1, 5, 6] 
print(bubble_sort(valores))



# Exemplo de Insertion Sort em Python 
def insertion_sort(lista): 
    for i in range(1, len(lista)): 
        chave = lista[i] 
        j = i - 1 
        while j >= 0 and chave < lista[j]: 
            lista[j + 1] = lista[j] 
            j -= 1 
        lista[j + 1] = chave 
    return lista 
 
valores = [12, 11, 13, 5, 6] 
print(insertion_sort(valores))




# Exemplo de Merge Sort em Python 
def merge_sort(lista): 
    if len(lista) <= 1: 
        return lista 
    meio = len(lista) // 2 
    esquerda = merge_sort(lista[:meio]) 
    direita = merge_sort(lista[meio:]) 
    return merge(esquerda, direita) 
 
def merge(esquerda, direita): 
    resultado = [] 
    i = j = 0 
    while i < len(esquerda) and j < len(direita): 
        if esquerda[i] < direita[j]: 
            resultado.append(esquerda[i]) 
            i += 1 
        else: 
            resultado.append(direita[j]) 
            j += 1 
    resultado += esquerda[i:] 
    resultado += direita[j:] 
    return resultado 
 
valores = [38, 27, 43, 3, 9, 82, 10] 
print(merge_sort(valores))





# Exemplo de Quick Sort em Python 
def quick_sort(lista): 
   if len(lista) <= 1: 
       return lista 
   else: 
       pivo = lista[0] 
       menores = [x for x in lista[1:] if x <= pivo] 
       maiores = [x for x in lista[1:] if x > pivo] 
       return quick_sort(menores) + [pivo] + quick_sort(maiores) 
 
valores = [10, 7, 8, 9, 1, 5] 
print(quick_sort(valores)) 



def busca_linear(lista, valor): 
   for i in range(len(lista)): 
       if lista[i] == valor: 
           return i  # retorna a posição 
   return -1  # não encontrado 
 
produtos = ["caderno", "caneta", "lapiseira", "borracha"] 
item = "lapiseira" 
pos = busca_linear(produtos, item) 
print(f"Item '{item}' encontrado na posição {pos}.") 





def busca_binaria(lista, valor): 
   inicio = 0 
   fim = len(lista) - 1 
 
   while inicio <= fim: 
       meio = (inicio + fim) // 2 
       if lista[meio] == valor: 
           return meio 
       elif lista[meio] < valor: 
           inicio = meio + 1 
       else: 
           fim = meio - 1 
   return -1 
 
numeros = [2, 4, 6, 8, 10, 12, 14, 16] 
print("Índice do número 10:", busca_binaria(numeros, 10)) 




vacinas = { 
   "João": "Pfizer", 
   "Maria": "Coronavac", 
   "Lucas": "Moderna" 
} 
 
print("Vacina da Maria:", vacinas["Maria"]) 


import pandas as pd 
 
df = pd.DataFrame({ 
   'nome': ['João', 'Maria', 'Lucas'], 
   'idade': [25, 30, 22], 
   'vacina': ['Pfizer', 'Coronavac', 'Moderna'] 
}) 
 
resultado = df[df['vacina'] == 'Coronavac'] 
print(resultado) 




faltantes = df[df['vacina'].isnull()] 
print("Registros sem informação de vacina:") 
print(faltantes) 








def merge_sort(lista): 
   if len(lista) <= 1: 
       return lista 
 
   meio = len(lista) // 2 
   esquerda = merge_sort(lista[:meio]) 
   direita = merge_sort(lista[meio:]) 
 
   return merge(esquerda, direita) 
 
def merge(esquerda, direita): 
   resultado = [] 
   i = j = 0 
 
   while i < len(esquerda) and j < len(direita): 
       if esquerda[i] < direita[j]: 
           resultado.append(esquerda[i]) 
           i += 1 
       else: 
           resultado.append(direita[j]) 
           j += 1 
 
   resultado += esquerda[i:] 
   resultado += direita[j:] 
   return resultado 
 
# Exemplo de uso 
numeros = [38, 27, 43, 3, 9, 82, 10] 
print(merge_sort(numeros)) 




def busca_binaria(lista, alvo): 
   esquerda, direita = 0, len(lista) - 1 
 
   while esquerda <= direita: 
       meio = (esquerda + direita) // 2 
       if lista[meio] == alvo: 
           return meio 
       elif lista[meio] < alvo: 
           esquerda = meio + 1 
       else: 
           direita = meio - 1 
   return -1 





from multiprocessing import Pool 
 
def processar_parte(arquivo): 
   import pandas as pd 
   df = pd.read_csv(arquivo) 
   # Simulação de processamento 
   return df.describe() 
 
arquivos = ['dados_jan.csv', 'dados_fev.csv', 'dados_mar.csv'] 
 
with Pool() as p: 
   resultados = p.map(processar_parte, arquivos) 


# Recursão simples (ineficiente) 
def fibonacci(n): 
   if n <= 1: 
       return n 
   return fibonacci(n-1) + fibonacci(n-2) 
 

from functools import lru_cache 
 
@lru_cache(maxsize=None) 
def fibonacci_eficiente(n): 
   if n <= 1: 
       return n 
   return fibonacci_eficiente(n-1) + fibonacci_eficiente(n-2) 




from sklearn.ensemble import RandomForestClassifier 
from sklearn.datasets import load_iris 
 
X, y = load_iris(return_X_y=True) 
modelo = RandomForestClassifier(n_estimators=10) 
modelo.fit(X, y) 




import pandas as pd 
 
df = pd.read_csv('chamadas.csv') 
 
# Dividindo em subgrupos 
grupos = df.groupby('tipo_ocorrencia') 
 
for tipo, grupo in grupos: 
   print(f"Analisando grupo: {tipo}") 
   print(grupo.describe()) 




def mochila_fracionaria(itens, capacidade): 
    itens.sort(key=lambda x: x[1]/x[0], reverse=True)  # ordena por valor/peso 
    total = 0 
    for peso, valor in itens: 
        if capacidade >= peso: 
            capacidade -= peso 
            total += valor 
        else: 
            total += valor * (capacidade / peso) 
            break 
    return total 
 
# (peso, valor) 
itens = [(10, 60), (5, 30), (15, 90)] 
print(mochila_fracionaria(itens, 15))  # resultado ótimo: 120.0




def mochila_01(pesos, valores, capacidade): 
   n = len(pesos) 
   dp = [[0]*(capacidade + 1) for _ in range(n + 1)] 
 
   for i in range(1, n + 1): 
       for w in range(capacidade + 1): 
           if pesos[i-1] <= w: 
               dp[i][w] = max(valores[i-1] + dp[i-1][w - pesos[i-1]], dp[i-1][w]) 
           else: 
               dp[i][w] = dp[i-1][w] 
 
   return dp[n][capacidade] 
 
# Exemplo: 
pesos = [2, 3, 4, 5] 
valores = [3, 4, 5, 6] 
capacidade = 5 
print(mochila_01(pesos, valores, capacidade))  # Deve retornar 7 







def troco_guloso(valor): 
   moedas = [0.50, 0.25, 0.10, 0.05, 0.01] 
   resultado = [] 
   for m in moedas: 
       while valor >= m: 
           valor = round(valor - m, 2)  # para evitar erros com ponto flutuante 
           resultado.append(m) 
   return resultado 
 
print(troco_guloso(1.00)) 




def fibonacci_iterativo(n): 
   if n <= 1: 
       return n 
   fib = [0, 1] 
   for i in range(2, n+1): 
       fib.append(fib[i-1] + fib[i-2]) 
   return fib[n]



from functools import lru_cache 
 
@lru_cache(maxsize=None) 
def fibonacci_pd(n): 
   if n <= 1: 
       return n 
   return fibonacci_pd(n-1) + fibonacci_pd(n-2) 
 
print(fibonacci_pd(50)) 





def fibonacci(n): 
   if n <= 1: 
       return n 
   return fibonacci(n-1) + fibonacci(n-2) 



A --- B 
|     | 
C --- D 




grafo = { 
   'A': ['B', 'C'], 
   'B': ['A', 'D'], 
   'C': ['A', 'D'], 
   'D': ['B', 'C'] 
} 



# 0 = sem conexão, 1 = conectado 
grafo = [ 
  [0, 1, 1, 0], 
   [1, 0, 0, 1], 
   [1, 0, 0, 1], 
   [0, 1, 1, 0] 
] 



from collections import deque 
 
def bfs(grafo, inicio): 
   visitados = set() 
   fila = deque([inicio]) 
 
   while fila: 
       atual = fila.popleft() 
       if atual not in visitados: 
           print(atual) 
           visitados.add(atual) 
           fila.extend([viz for viz in grafo[atual] if viz not in visitados]) 



def dfs(grafo, atual, visitados=None): 
   if visitados is None: 
       visitados = set() 
   visitados.add(atual) 
   print(atual) 
   for vizinho in grafo[atual]: 
       if vizinho not in visitados: 
           dfs(grafo, vizinho, visitados) 





import heapq 
 
def dijkstra(grafo, inicio): 
   dist = {no: float('inf') for no in grafo} 
   dist[inicio] = 0 
   fila = [(0, inicio)] 
 
   while fila: 
       atual_dist, atual_no = heapq.heappop(fila) 
       for vizinho, peso in grafo[atual_no]: 
           nova_dist = atual_dist + peso 
           if nova_dist < dist[vizinho]: 
               dist[vizinho] = nova_dist 
               heapq.heappush(fila, (nova_dist, vizinho)) 
 
   return dist 
 
# Grafo com pesos 
grafo = { 
   'A': [('B', 1), ('C', 4)], 
   'B': [('A', 1), ('C', 2), ('D', 5)], 
   'C': [('A', 4), ('B', 2), ('D', 1)], 
   'D': [('B', 5), ('C', 1)] 
} 
 
print(dijkstra(grafo, 'A')) 



