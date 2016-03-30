# -*- coding: utf-8 -*-
from sys import stdout
import os, re, json, argparse
from selenium import webdriver
from selenium.webdriver.support.ui import Select
import sqlite3
from unidecode import unidecode
from sklearn.externals import joblib
from sframe import SFrame
from fuzzywuzzy import process
from string import punctuation
from unicodedata import normalize
from time import sleep


def printover(text):
    stdout.write('\r' + text + ' ' * (60 - len(text)))
    stdout.flush()  # important


def preprocessor(text):
    text = normalize('NFKD', text.lower()).encode('ASCII', 'ignore')  # minusculos e tira acentuacao
    text = text.translate(None, punctuation)  # tira pontuacao
    text = re.sub('\s{2,}', ' ', text)  # tira espacos duplos
    return text


def fuzzynome(text):
    if re.search("(?:\W(me|epp)$)", text):  #  Se for ME ou EPP
        return -1
    else:
        semente, porcentagem = process.extractOne(text, seeds['Stem'])
        if porcentagem > 90:
            return seeds[seeds['Stem'] == semente]['RaizCNPJ'][0]
        else:
            return -1


def get_timeout(link_text):
    problema = False
    def link_has_gone_stale():
        try:
            # poll the link with an arbitrary call
            browser.get(link_text)
            browser.find_element_by_id('pbEnviar')
            if problema:
                print('\nBusca normalizada. Retomando Scrap.')
            return False
        except:
            printover('\n')
            return True
    i = 0
    while link_has_gone_stale():
        i += 1
        printover('Ultima busca: %s Tentando conexao em 60s... %d tentativa' % (busca, i))
        problema = True
        sleep(60)


def buscaprocesso(busca):
            get_timeout(url0)
            erro = 0
            busca = busca.strip().decode('utf8')
            if hasattr(args, 'n') and args.n:
                Select(browser.find_element_by_name('cbPesquisa')).select_by_value(args.n)  # Tipo de pesquisa
            if args.n == 'NUMPROC':  ## Muda a busca para numero do processo completto
                xpath = ".//*[@id='radioNumeroAntigo']"
                browser.find_element_by_xpath(xpath).click()
                xpath = './/*[@id="nuProcessoAntigoFormatado"]'
                browser.find_element_by_xpath(xpath).send_keys(busca)
            else:
                xpath = ".//*[@id='" + args.n + "']/td[2]/table/tbody/tr/td/input[1]"
                browser.find_element_by_xpath(xpath).send_keys(busca)  #  seleciona o tipo de busca

            browser.find_element_by_id('pbEnviar').click()  # Busca

            items = []
            try:
                url_tpl = browser.find_element_by_partial_link_text('>>').get_attribute('href')
                last = int(re.search('paginaConsulta=(\d+)', url_tpl).group(1))
                url_tpl = re.sub('paginaConsulta=\d+', 'paginaConsulta={}', url_tpl)

                print "Start parsing search pages"

                for i in xrange(1, last + 1):
                    printover("[%d / %d]" % (i, last))
                    get_timeout(url_tpl.format(i))
                    links = browser.find_elements_by_css_selector('a.linkProcesso')
                    getlinks = [link.get_attribute('href') for link in links if not (args.i and existeprocesso(link.text))]
                    items += getlinks
            except:
                if browser.find_elements_by_xpath(
                        ".//*[@id='spwTabelaMensagem']/table[1]/tbody/tr[1]/td[2]"):  # Mensagem de alerta
                    return
                links = browser.find_elements_by_css_selector('a.linkProcesso')  # Sem paginas < 11 processos
                getlinks = [link.get_attribute('href') for link in links]
                items += getlinks
            numitems = len(items)
            if numitems < 1:
                items = [1]
            for n, item in enumerate(items):
                try:
                    campos = {}
                    if item != 1:  # Se existir mais de um processo
                        get_timeout(item)
                    if numitems > 0:
                        printover("[%d / %d] Parsing url %s\r" % (n + 1, numitems, item))
                    for (i, line) in enumerate(
                            browser.find_elements_by_xpath("html/body/table[4]/tbody/tr/td/div[1]/table[2]/tbody/tr")):
                        linha = line.text.split(':')
                        if len(linha) > 1:
                            campos.update({unidecode(linha[0].strip()).lower(): linha[1].strip()})
                        else:
                            campos.update({i: linha[0].strip()})
                    if len(linha) > 1:
                        campos.update({unidecode(linha[0].strip()).lower(): linha[1].strip()})
                    else:
                        campos.update({i: linha[0].strip()})
                    dadosprocesso = campos.get('processo').split()
                    processo = dadosprocesso[0]
                    printover('Processo: %s' % processo)
                    status = None
                    if len(dadosprocesso) > 1:  # Se houver situacao
                        try:
                            status = browser.find_element_by_xpath("html/body/table[4]/tbody/tr/td/div[1]/table[2]/tbody/tr[1]/td[2]/table/tbody/tr/td/span[3]").text
                        except:
                            pass
                    pid = re.sub('\D', '', processo)
                    pid = pid[0:7] + pid[9:]
                    classe = campos.get('classe')
                    assunto = campos.get('assunto')
                    area = campos.get('area')
                    dataini = campos.get('distribuicao').split()[0]
                    dataini = int(dataini[6:] + dataini[3:5] + dataini[0:2])  # transforma data em numero yyyymmdd
                    valor = campos.get('valor da acao')
                    if valor is not None:
                        valor = float(valor.split()[1].replace('.', '').replace(',', '.'))
                    prioridade = unidecode(browser.find_element_by_xpath("html/body/table[4]/tbody/tr/td/div[1]/table[2]/tbody/tr[2]/td[2]/table/tbody/tr/td/span").text) == '(Tramitacao prioritaria)'
                    vara = None
                    foro = None
                    for key in campos.keys():
                        if (('Foro' or 'DEECRIM') in campos.get(key)) and type(key) == int:
                            varaforo = campos.get(int(key)).split('-')  # Se processo for prioritario tem uma linha a mais
                            vara = (varaforo[0]).strip()
                            foro = (varaforo[1]).strip()
                            break
                    juiz = campos.get('juiz')
                except:
                    if 'processo' not in locals():
                        processo = ''
                    erro = errohtml(erro, processo, args.n, busca, item)
                    continue  # Continua (pula) caso excecao por mal formacao no html

                    # Partes e Advogados
                requerente = ''
                requerido = ''
                advs_rte = [None, None, None]
                advs_rdo = [None, None, None]

                try:
                    # Promoventes
                    partes = browser.find_elements_by_xpath(".//*[@id='tablePartesPrincipais']/tbody/tr[1]/td[2]")[
                        0].text.split('\n')
                    requerente = partes[0]
                    for p in range(1, len(partes)):
                        adv = partes[p].split(':')
                        if adv[0][:3].lower() == 'adv':
                            advs_rte[p - 1] = adv[1].strip()
                except:
                    pass

                try:
                    # Promovidos
                    partes = browser.find_elements_by_xpath(".//*[@id='tablePartesPrincipais']/tbody/tr[2]/td[2]")[
                        0].text.split('\n')
                    requerido = partes[0]
                    for p in range(1, len(partes)):
                        adv = partes[p].split(':')
                        if adv[0][:3].lower() == 'adv':
                            advs_rdo[p - 1] = adv[1].strip()
                except:
                    pass

                #  ML do requerente/requerido
                if requerente != '':
                    prequerente = preprocessor(requerente)
                    pessoa_rte = classificar(prequerente)
                    if pessoa_rte == 1:
                        raiz_requerente = fuzzynome(prequerente)
                    else:
                        raiz_requerente = -1
                else:
                    pessoa_rte = 0
                    raiz_requerente= -1

                if requerido != '':
                    prequerido = preprocessor(requerido)
                    pessoa_rdo = classificar(prequerido)
                    if pessoa_rdo == 1:
                        raiz_requerido = fuzzynome(prequerido)
                    else:
                        raiz_requerido = -1
                else:
                    pessoa_rdo = 0
                    raiz_requerido = -1


                # Escreve registro do processo
                # Start SQL connection
                conn = sqlite3.connect('tjsp.sqlite')
                cur = conn.cursor()
                try:
                    cur.execute(
                        '''INSERT OR REPLACE INTO ft_processo ( pid, processo, dataini, vara, foro, classe, valor, juiz,
                        adv_rte1, adv_rte2, adv_rte3, adv_rdo1, adv_rdo2, adv_rdo3, requerente, requerido, prioridade,
                        area, pessoa_rte, pessoa_rdo, raiz_requerente, raiz_requerido, status, assunto ) VALUES ( ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ? ) ''',
                        (pid, processo, dataini, vara, foro, classe, valor, juiz, advs_rte[0], advs_rte[1], advs_rte[2],
                         advs_rdo[0], advs_rdo[1], advs_rdo[2], requerente, requerido, prioridade, area,
                         pessoa_rte, pessoa_rdo, raiz_requerente, raiz_requerido, status, assunto))
                except:
                    erro = errohtml(erro, processo, args.n, busca, item)

                # Movimentacoes
                if not args.p:
                    try:
                        browser.find_element_by_xpath(".//*[@id='linkmovimentacoes']").click()
                        xpathmov = ".//*[@id='tabelaTodasMovimentacoes']/tbody/tr"
                        movimentacoes = browser.find_elements_by_xpath(xpathmov)
                    except:
                        xpathmov = ".//*[@id='tabelaUltimasMovimentacoes']/tbody/tr"
                        movimentacoes = browser.find_elements_by_xpath(xpathmov)
                    nm = len(movimentacoes)
                    if nm > 500:
                        nm = 500
                    movreg = ((pid,
                               movimentacao[1].text[6:10] + movimentacao[1].text[3:5] + movimentacao[1].text[0:2],
                               nm - movimentacao[0],
                               movimentacao[1].text[11:])
                              for movimentacao in enumerate(movimentacoes))
                    cur.executemany('''INSERT OR IGNORE INTO ft_movimentacoes ( pid, data, numero, texto ) VALUES ( ?, ?, ?, ? ) ''', movreg)
                conn.commit()
                conn.close()
            return numitems, erro


def existeprocesso(processo):
    # Start SQL connection
    conn = sqlite3.connect('tjsp.sqlite')
    curr = conn.cursor()
    idprocesso = re.sub('\D', '', processo)
    idprocesso = int(idprocesso[0:7] + idprocesso[9:])
    curr.execute('SELECT 1 FROM ft_processo WHERE pid = ?', (idprocesso, ))
    resultado = curr.fetchone()
    try:
        return (resultado is not None)
    finally:
        conn.close()


def errohtml(erro, processo='', tipobusca='', busca='', url=''):
    erro += 1
    # Start SQL connection
    conn = sqlite3.connect('tjsp.sqlite')
    cur = conn.cursor()
    cur.execute('''INSERT OR REPLACE INTO ft_erroscrap
                ( processo, url, tipobusca, busca ) VALUES ( ?, ?, ?, ? ) ''',
                (processo, url, tipobusca, busca))
    conn.commit()
    conn.close()
    print('\nErros ate o momento: %d' % erro)
    return erro


def classificar(pessoa):
    return lr_clf.predict([pessoa])[0]


#  Programa principal

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='main.py -q "query for search"')
    parser.add_argument('-q', action='store', type=str)  # Texto da Pesquisa
    parser.add_argument('-f', action='store', type=str)  # Foro (ver arquivo ListadeForos.csv)
    parser.add_argument('-a', action='store', type=str)  # Arquivo de criterios de busca (formato csv)
    parser.add_argument('-i', action='store_true')  # Ignora processo existente
    parser.add_argument('-p', action='store_true')  # Atualiza somente dados do processo ignorando as movimentacoes
    parser.add_argument('-n', action='store', type=str)  # Tipo de pesquisa:
    # NUMPROC : Número do Processo
    # NMPARTE : Nome da parte
    # DOCPARTE : Documento da Parte
    # NMADVOGADO : Nome do Advogado
    # NUMOAB : OAB
    # PRECATORIA : N° da Carta Precatória na Origem
    # DOCDELEG : N° do Documento na Delegacia
    # NUMCDA : CDA



    args = parser.parse_args()

    if (hasattr(args, 'n') and args.n) and ((hasattr(args, 'q') and args.q) or (hasattr(args, 'a') and args.a)):

        symlink_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dwnl')

        print("Initializing browser...")

        url0 = 'http://esaj.tjsp.jus.br/cpopg/open.do'

        with open('webdriver_prefs.json', 'r') as f:
            webdriver.FirefoxProfile.DEFAULT_PREFERENCES = json.load(f)

        profile = webdriver.FirefoxProfile()
        profile.set_preference('browser.download.folderList', 2)
        profile.set_preference('browser.download.dir', symlink_path)
        profile.set_preference('browser.helperApps.neverAsk.saveToDisk',
                               'text/html,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        profile.set_preference('pdfjs.disabled', True)

        browser = webdriver.Firefox(profile)
        #  load classifier
        lr_clf = joblib.load('./model/pfpj_classifier.pkl')

        totalprocessos = 0
        totalerros = 0

        seeds = SFrame.read_csv('seedSP.csv', verbose=False, column_type_hints=[str, str, int])
        del seeds['Seed']

        if hasattr(args, 'a') and args.a:
            fh = open(args.a, 'r')
            numprocessos, numerro = [buscaprocesso(busca) for busca in fh.readlines()]
            fh.close
            totalprocessos += numprocessos
            totalerros += numerro
        else:
            buscas = args.q
            totalprocessos, totalerros = buscaprocesso(buscas)
            totalbuscas = 1

        print("Parsing has been done")
        print('Total de erros / processos: %d / %d:' % (totalerros, totalprocessos))

        browser.close()

    else:
        print("Expected parameters. Use main.py --help for more information")
